import logging
import re
import datetime
from urllib.parse import urlencode

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models import Count
from django.db.models.functions import Length
from .forms import NotificationPreferenceForm
from .models import (
    GeneratedBet, HitNotification, NotificationPreference, LotteryResult, GenerationRule,
    GAMES_CONFIG, GAMES_WITH_SEQUENCE_RULE, RULE_DEFINITIONS, RULE_NAMES_BY_GAME,
    SEQUENCE_RULE_NAMES, DISTRIBUTION_CHOICES, GAME_GRID,
)
from .utils import (
    generate_bet_with_relaxation, check_duplicate_bet, count_sequential_pairs,
    calculate_statistics, normalize_numbers, calculate_bet_prize,
    fetch_cef_result, suggest_next_contest, apply_prize_to_bet, normalize_contest
)

logger = logging.getLogger(__name__)


def _block_if_contest_already_drawn(request, game, contest, redirect_to='home', **redirect_kwargs):
    """Bloqueia com mensagem clara se o Jogo+Concurso ja tem resultado oficial (de qualquer
    usuario) -- devolve um redirect pronto se bloqueado, ou None se pode seguir."""
    if LotteryResult.objects.filter(game=game, contest=contest).exists():
        messages.error(request, f'O concurso {contest} de {game} ja foi sorteado. Escolha outro concurso.')
        return redirect(redirect_to, **redirect_kwargs)
    return None


def home(request):
    """Pagina inicial com dashboard."""
    if request.user.is_authenticated:
        total_bets = GeneratedBet.objects.filter(user=request.user).count()
        bets_by_type = GeneratedBet.objects.filter(user=request.user).values('game').annotate(
            total=Count('id')
        ).order_by('-total')

        recent_bets = GeneratedBet.objects.filter(user=request.user)[:10]
        suggested_contests = {
            game_name: suggest_next_contest(game_name) for game_name in GAMES_CONFIG
        }

        context = {
            'total_jogos': total_bets,
            'jogos_por_tipo': bets_by_type,
            'ultimos_jogos': recent_bets,
            'jogos_disponiveis': GAMES_CONFIG,
            'concursos_sugeridos': suggested_contests,
        }
    else:
        context = {
            'jogos_disponiveis': GAMES_CONFIG,
        }

    return render(request, 'loterias_core/home.html', context)


@login_required
def create_bet_view(request):
    """View para gerar novo jogo."""
    if request.method != 'POST':
        return redirect('home')

    selected_game = request.POST.get('jogo')
    contest = request.POST.get('concurso', '').strip()

    if not selected_game or not contest:
        messages.error(request, 'Selecione o jogo e informe o numero do concurso.')
        return redirect('home')

    if selected_game not in GAMES_CONFIG:
        messages.error(request, 'Jogo invalido.')
        return redirect('home')

    try:
        contest = normalize_contest(contest)
    except ValueError:
        messages.error(request, f'Numero de concurso invalido: {contest}.')
        return redirect('home')

    blocked = _block_if_contest_already_drawn(request, selected_game, contest)
    if blocked:
        return blocked

    # Jogos repetidos sao permitidos (mesmo Concurso ou varios Concursos): nao ha checagem de duplicata.
    new_bet, new_clovers, relaxed_rule = generate_bet_with_relaxation(selected_game, request.user)

    if not new_bet:
        messages.warning(request, f'Nao foi possivel gerar um jogo de {selected_game} com as suas regras de geracao. Ajuste as regras deste jogo e tente de novo.')
        return redirect('home')

    # Calcular pares sequenciais
    sequential_pairs_count = count_sequential_pairs(new_bet)

    # Salvar no banco de dados
    bet = GeneratedBet.objects.create(
        user=request.user,
        game=selected_game,
        contest=contest,
        numbers=new_bet,
        clovers=new_clovers if new_clovers else [],
        sequential_pairs=sequential_pairs_count
    )

    messages.success(request, f'Jogo de {selected_game} gerado com sucesso para o concurso {contest}!')
    if relaxed_rule:
        messages.warning(request, _relaxed_rule_message(selected_game, relaxed_rule))

    return redirect('bet_detail', pk=bet.pk)


@login_required
def bet_detail_view(request, pk):
    """Pagina de detalhes de um jogo."""
    bet = get_object_or_404(GeneratedBet, pk=pk, user=request.user)

    previous_bets = GeneratedBet.objects.filter(
        user=request.user,
        game=bet.game
    ).exclude(pk=pk).order_by('-created_at')[:5]

    official_result = LotteryResult.objects.filter(game=bet.game, contest=bet.contest).first()
    prize_info = None
    if official_result:
        prize_info = calculate_bet_prize(
            bet.game,
            bet.numbers,
            bet.clovers,
            {
                'numbers': official_result.numbers,
                'clovers': official_result.clovers,
                'prizes': official_result.prizes,
                'numbers_second_draw': official_result.numbers_second_draw,
                'prizes_second_draw': official_result.prizes_second_draw,
                'captured_at': official_result.captured_at,
            }
        )

    context = {
        'jogo': bet,
        'jogos_anteriores': previous_bets,
        'aplica_regra_sequencia': bet.game in GAMES_WITH_SEQUENCE_RULE,
        'resultado_oficial': official_result,
        'premio_info': prize_info,
    }

    return render(request, 'loterias_core/bet_detail.html', context)


def _parse_date(value):
    try:
        return datetime.date.fromisoformat(value) if value else None
    except ValueError:
        return None


@login_required
def history_view(request):
    """Historico de jogos com filtros cumulativos (AND) via querystring (Story 4.8, FR-24)."""
    bets_list = GeneratedBet.objects.filter(user=request.user)
    params = {}
    active_filters = []

    game_filter = request.GET.get('jogo')
    if game_filter in GAMES_CONFIG:
        bets_list = bets_list.filter(game=game_filter)
        params['jogo'] = game_filter
        active_filters.append(('jogo', f'Jogo: {game_filter}'))
    else:
        game_filter = None

    tz = timezone.get_current_timezone()
    date_from = _parse_date(request.GET.get('de'))
    date_to = _parse_date(request.GET.get('ate'))
    if date_from:
        start = datetime.datetime.combine(date_from, datetime.time.min, tzinfo=tz)
        bets_list = bets_list.filter(created_at__gte=start)
        params['de'] = date_from.isoformat()
        active_filters.append(('de', f'De: {date_from.strftime("%d/%m/%Y")}'))
    if date_to:
        end = datetime.datetime.combine(date_to, datetime.time.max, tzinfo=tz)
        bets_list = bets_list.filter(created_at__lte=end)
        params['ate'] = date_to.isoformat()
        active_filters.append(('ate', f'Até: {date_to.strftime("%d/%m/%Y")}'))

    only_winners = request.GET.get('premiado') == '1'
    if only_winners:
        bets_list = bets_list.filter(prize__gt=0)
        params['premiado'] = '1'
        active_filters.append(('premiado', 'Só premiados'))

    valid_orderings = {'-created_at', 'created_at', 'game', 'contest'}
    ordering = request.GET.get('ordenacao', '-created_at')
    if ordering not in valid_orderings:
        ordering = '-created_at'
    if ordering == 'contest':  # contest e texto: ordena por tamanho e depois lexicograficamente
        bets_list = bets_list.order_by(Length('contest'), 'contest', 'pk')
    else:
        bets_list = bets_list.order_by(ordering, '-pk')
    if ordering != '-created_at':
        params['ordenacao'] = ordering

    def _querystring(exclude=None):
        return urlencode({k: v for k, v in params.items() if k != exclude})

    paginator = Paginator(bets_list, 20)
    bets = paginator.get_page(request.GET.get('page'))

    context = {
        'jogos': bets,
        'jogos_disponiveis': GAMES_CONFIG,
        'jogo_filtro': game_filter,
        'data_de': params.get('de', ''),
        'data_ate': params.get('ate', ''),
        'somente_premiados': only_winners,
        'ordenacao': ordering,
        'filtros_ativos': [
            {'label': label, 'remove_qs': _querystring(exclude=key)} for key, label in active_filters
        ],
        'tem_filtros': bool(active_filters),
        'querystring': _querystring(),
    }

    return render(request, 'loterias_core/history.html', context)


@login_required
@require_POST
def save_manual_bet_view(request):
    """Salva um jogo manual informado pelo usuario."""
    selected_game = request.POST.get('jogo')
    contest = request.POST.get('concurso', '').strip()
    raw_numbers = request.POST.get('numeros', '').strip()

    if not selected_game or not contest or not raw_numbers:
        messages.error(request, 'Preencha o jogo, concurso e numeracao do jogo manual.')
        return redirect('home')

    if selected_game not in GAMES_CONFIG:
        messages.error(request, 'Jogo invalido.')
        return redirect('home')

    try:
        contest = normalize_contest(contest)
    except ValueError:
        messages.error(request, f'Numero de concurso invalido: {contest}.')
        return redirect('home')

    numbers = sorted(normalize_numbers(raw_numbers))
    config = GAMES_CONFIG[selected_game]
    expected = config['bets_count']

    if len(numbers) != expected:
        messages.error(request, f'Este jogo exige {expected} numeros. Voce informou {len(numbers)}.')
        return redirect('home')

    minimum = 1
    maximum = config['numbers_count']
    if any(num < minimum or num > maximum for num in numbers):
        messages.error(request, f'Os numeros devem estar entre {minimum} e {maximum} para {selected_game}.')
        return redirect('home')

    blocked = _block_if_contest_already_drawn(request, selected_game, contest)
    if blocked:
        return blocked

    sequential_pairs_count = count_sequential_pairs(numbers)
    bet = GeneratedBet.objects.create(
        user=request.user,
        game=selected_game,
        contest=contest,
        numbers=numbers,
        clovers=[],
        sequential_pairs=sequential_pairs_count,
        manual=True,
    )

    result = fetch_cef_result(selected_game, contest)
    if result:
        LotteryResult.objects.update_or_create(
            game=selected_game,
            contest=contest,
            defaults={
                'numbers': result.get('numbers', []),
                'clovers': result.get('clovers', []),
                'prizes': result.get('prizes', {}),
                'numbers_second_draw': result.get('numbers_second_draw', []),
                'prizes_second_draw': result.get('prizes_second_draw', {}),
                'source': 'CEF',
            }
        )
        prize = calculate_bet_prize(selected_game, bet.numbers, bet.clovers, result)
        apply_prize_to_bet(bet, prize)
        if prize['won']:
            messages.success(request, f'Jogo manual salvo e verificado com {prize["hits"]} acertos. Premio: {prize["value"]}.')
        else:
            messages.info(request, f'Jogo manual salvo. Resultado oficial consultado; sem premio para este jogo e concurso.')
    else:
        messages.success(request, f'Jogo manual salvo com sucesso para o concurso {contest}.')

    return redirect('bet_detail', pk=bet.pk)


@login_required
def check_bet_result_view(request, pk):
    """Consulta o resultado oficial da CEF para um jogo do usuario e atualiza premio."""
    bet = get_object_or_404(GeneratedBet, pk=pk, user=request.user)
    result = fetch_cef_result(bet.game, bet.contest)

    if not result:
        messages.warning(request, 'Nao foi possivel consultar o resultado oficial da CEF neste momento.')
        return redirect('bet_detail', pk=pk)

    LotteryResult.objects.update_or_create(
        game=bet.game,
        contest=bet.contest,
        defaults={
            'numbers': result.get('numbers', []),
            'clovers': result.get('clovers', []),
            'prizes': result.get('prizes', {}),
            'numbers_second_draw': result.get('numbers_second_draw', []),
            'prizes_second_draw': result.get('prizes_second_draw', {}),
            'source': 'CEF',
        }
    )

    prize = calculate_bet_prize(bet.game, bet.numbers, bet.clovers, result)
    apply_prize_to_bet(bet, prize)

    if prize['won']:
        messages.success(request, f'Verificacao concluida: {prize["hits"]} acertos e premio de {prize["value"]}.')
    else:
        messages.info(request, f'Verificacao concluida: {prize["hits"]} acertos. Sem premio identificado para este concurso.')

    return redirect('bet_detail', pk=pk)


@login_required
def regenerate_bet_view(request, pk):
    """Refaz um jogo existente gerando novos numeros -- substitui o GeneratedBet original in-place
    (Story 2.17), nunca cria um segundo registro pro mesmo Jogo+Concurso."""
    original_bet = get_object_or_404(GeneratedBet, pk=pk, user=request.user)

    blocked = _block_if_contest_already_drawn(request, original_bet.game, original_bet.contest, redirect_to='bet_detail', pk=pk)
    if blocked:
        return blocked

    # Jogos repetidos sao permitidos (mesmo Concurso ou varios Concursos): nao ha checagem de duplicata.
    new_bet, new_clovers, relaxed_rule = generate_bet_with_relaxation(original_bet.game, request.user)

    if not new_bet:
        messages.warning(request, f'Nao foi possivel refazer o jogo de {original_bet.game} com as suas regras de geracao. Ajuste as regras deste jogo e tente de novo.')
        return redirect('bet_detail', pk=pk)

    sequential_pairs_count = count_sequential_pairs(new_bet)

    # Story 2.17: substitui o jogo original in-place, em vez de criar um segundo registro pro
    # mesmo Jogo+Concurso -- "Refazer" troca os numeros do jogo (o usuario pode gerar quantos jogos quiser pelo mesmo
    # concurso pelo botao Gerar; ver Story 2.20).
    # manual=False porque o jogo agora e algoritmico, nao mais o que o usuario digitou; os campos
    # de verificacao sao resetados porque o numero mudou -- qualquer hits/prize antigo pertence ao
    # jogo anterior, nunca ao novo (alcancavel mesmo com _block_if_contest_already_drawn: a purga
    # manual da Story 2.10 pode apagar o LotteryResult de um par sem HitNotification associada,
    # ex. um bet verificado sem premio, deixando result_checked/hits/prize obsoletos no GeneratedBet
    # enquanto o bloqueio nao acusa mais nada).
    original_bet.numbers = new_bet
    original_bet.clovers = new_clovers if new_clovers else []
    original_bet.sequential_pairs = sequential_pairs_count
    original_bet.manual = False
    original_bet.result_checked = False
    original_bet.hits = 0
    original_bet.prize = 0
    original_bet.prize_description = ''
    HitNotification.objects.filter(bet=original_bet).delete()
    original_bet.save()

    messages.success(request, f'Novo jogo de {original_bet.game} gerado com sucesso!')
    if relaxed_rule:
        messages.warning(request, _relaxed_rule_message(original_bet.game, relaxed_rule))
    return redirect('bet_detail', pk=original_bet.pk)


@login_required
def statistics_view(request):
    """Pagina de estatisticas do usuario."""
    statistics_by_game = {}

    for game_name in GAMES_CONFIG.keys():
        stats = calculate_statistics(request.user, game_name)
        if stats:
            statistics_by_game[game_name] = stats

    # Estatisticas gerais
    total_bets = GeneratedBet.objects.filter(user=request.user).count()
    total_with_sequence = sum(stats['with_sequence'] for stats in statistics_by_game.values())
    total_without_sequence = sum(stats['without_sequence'] for stats in statistics_by_game.values())

    context = {
        'estatisticas': statistics_by_game,
        'total_geral': total_bets,
        'total_com_sequencia': total_with_sequence,
        'total_sem_sequencia': total_without_sequence,
        'jogos_disponiveis': GAMES_CONFIG,
    }

    return render(request, 'loterias_core/statistics.html', context)


@login_required
@require_POST
def delete_bet_view(request, pk):
    """Exclui um jogo do historico."""
    bet = get_object_or_404(GeneratedBet, pk=pk, user=request.user)
    bet.delete()
    messages.success(request, 'Jogo excluido com sucesso!')
    return redirect('history')


@login_required
def api_create_bet_view(request):
    """API endpoint para gerar jogo via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo nao permitido'}, status=405)

    import json
    data = json.loads(request.body)
    selected_game = data.get('jogo')
    contest = data.get('concurso', '').strip()

    if not selected_game or not contest:
        return JsonResponse({'error': 'Dados incompletos'}, status=400)

    if not isinstance(selected_game, str) or selected_game not in GAMES_CONFIG:
        return JsonResponse({'error': 'Jogo invalido'}, status=400)

    try:
        contest = normalize_contest(contest)
    except ValueError:
        return JsonResponse({'error': f'Numero de concurso invalido: {contest}'}, status=400)

    nums, clovers, relaxed_rule = generate_bet_with_relaxation(selected_game, request.user)
    if nums is None:
        return JsonResponse(
            {'error': 'Nao foi possivel gerar um jogo com as regras de geracao atuais'}, status=422,
        )
    sequential_pairs_count = count_sequential_pairs(nums)

    # Verificar repeticao
    is_duplicate = check_duplicate_bet(request.user, selected_game, nums, clovers)

    return JsonResponse({
        'numeros': nums,
        'trevos': clovers,
        'pares_sequenciais': sequential_pairs_count,
        'repetido': is_duplicate,
        'regra_relaxada': RULE_DEFINITIONS[relaxed_rule]['label'] if relaxed_rule else None,
    })


@login_required
def notifications_view(request):
    """Lista as notificacoes de acerto nao lidas do usuario, com os numeros batidos e o valor
    do premio por item, e a acao de marcar como lida (Story 2.5)."""
    notifications = HitNotification.objects.filter(
        bet__user=request.user, is_read=False
    ).select_related('bet')

    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)

    pairs = {(n.bet.game, n.bet.contest) for n in page}
    results_by_pair = {
        (r.game, r.contest): r
        for r in LotteryResult.objects.filter(
            game__in=[game for game, _ in pairs],
            contest__in=[contest for _, contest in pairs],
        )
    } if pairs else {}

    for notification in page:
        result = results_by_pair.get((notification.bet.game, notification.bet.contest))
        if result:
            # Reusa calculate_bet_prize (inclui o 2o sorteio da Dupla-Sena e os trevos), sem recalcular aqui.
            comparison = calculate_bet_prize(
                notification.bet.game, notification.bet.numbers, notification.bet.clovers,
                {
                    'numbers': result.numbers,
                    'clovers': result.clovers,
                    'prizes': result.prizes,
                    'numbers_second_draw': result.numbers_second_draw,
                    'prizes_second_draw': result.prizes_second_draw,
                    'captured_at': result.captured_at,
                },
            )
            notification.matched_numbers = comparison['matched_numbers']
            notification.matched_clovers = comparison['matched_clovers']
            notification.matched_draw = comparison['draw']
        else:
            logger.warning(
                'notifications_view: LotteryResult nao encontrado para %s/%s (notificacao %s)',
                notification.bet.game, notification.bet.contest, notification.pk,
            )
            notification.matched_numbers = []
            notification.matched_clovers = []
            notification.matched_draw = 1

    context = {
        'notificacoes': page,
    }
    return render(request, 'loterias_core/notificacoes.html', context)


@login_required
@require_POST
def mark_notification_read_view(request, pk):
    """Marca uma notificacao de acerto como lida. So afeta a notificacao do proprio usuario --
    um pk de outra pessoa (ou inexistente) simplesmente nao casa com o filtro, sem revelar se
    existe ou nao (mesmo redirect, sem erro, nos dois casos)."""
    HitNotification.objects.filter(pk=pk, bet__user=request.user).update(is_read=True)
    # Mensagem sempre exibida (sem checar quantas linhas foram afetadas) -- do contrario, a
    # ausencia da mensagem revelaria se aquele pk existe/pertence a outro usuario.
    messages.success(request, 'Notificacao marcada como lida.')
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('notifications')


@login_required
@require_http_methods(['GET', 'POST'])
def notification_preferences_view(request):
    """Tela de preferencia de canal de aviso de acerto (site e/ou e-mail)."""
    preference, _ = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = NotificationPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            form.save()
            messages.success(request, 'Preferencia de notificacao atualizada com sucesso!')
            return redirect('notification_preferences')
    else:
        form = NotificationPreferenceForm(instance=preference)

    context = {'form': form}
    return render(request, 'loterias_core/preferencias_notificacao.html', context)


# Jogos com grid do volante confirmado (PRD 8.5) -- so pra montar o texto de ajuda de linha/coluna.
_GRID_HELP = {
    'limit_row_count': 'Considera as linhas do volante oficial da {game} na Caixa ({rows} linhas x {cols} colunas).',
    'limit_column_count': 'Considera as colunas do volante oficial da {game} na Caixa ({rows} linhas x {cols} colunas).',
}


def _relaxed_rule_message(game, rule_name):
    """Aviso da regra relaxada (Story 4.5, FR-22) -- nomeia a regra e o Jogo, nunca generico."""
    label = RULE_DEFINITIONS[rule_name]['label']
    return (
        f"O jogo de {GAMES_CONFIG[game]['name']} foi gerado relaxando a regra '{label}' -- "
        f"nao foi possivel respeitar todas as regras configuradas."
    )


def _game_from_slug(slug):
    for game_name in GAMES_CONFIG:
        if game_name.lower() == slug:
            return game_name
    return None


def _build_rule_rows(game, saved_by_name, posted=None):
    """Monta as linhas do formulario a partir do que esta salvo ou, se houver POST invalido, do
    que foi enviado. Devolve (rows, has_errors)."""
    config = GAMES_CONFIG[game]
    rows = []
    has_errors = False
    for rule_name in RULE_NAMES_BY_GAME[game]:
        definition = RULE_DEFINITIONS[rule_name]
        saved = saved_by_name.get(rule_name)
        kind = definition['kind']
        stored_value = None
        if saved is not None:
            stored_value = saved.numeric_value if kind == 'int' else saved.choice_value
        row = {
            'rule_name': rule_name,
            'label': definition['label'],
            'kind': kind,
            'help': _GRID_HELP[rule_name].format(game=config['name'], rows=GAME_GRID[game][0], cols=GAME_GRID[game][1]) if rule_name in _GRID_HELP else '',
            'enabled': bool(saved and saved.enabled),
            'value': stored_value,
            'error': '',
            'max': config['numbers_count'],
            'choices': DISTRIBUTION_CHOICES if kind == 'choice' else None,
            'submitted_value': None,  # None = nao enviado (campo desabilitado): preserva o salvo
        }
        if posted is not None:
            row['enabled'] = f'enabled_{rule_name}' in posted
            raw = posted.get(f'value_{rule_name}')
            if raw is not None:
                raw = raw.strip()
                row['submitted_value'] = raw
                row['value'] = raw
            if row['enabled']:
                row['error'] = _validate_rule_value(kind, raw or '', config['numbers_count'])
                has_errors = has_errors or bool(row['error'])
        rows.append(row)
    return rows, has_errors


def _validate_rule_value(kind, raw, maximum):
    if kind == 'choice':
        if raw not in dict(DISTRIBUTION_CHOICES):
            return 'Escolha um tipo de distribuição.'
        return ''
    if not re.fullmatch(r'[0-9]{1,6}', raw) or not 1 <= int(raw) <= maximum:
        return f'Informe um número inteiro entre 1 e {maximum}.'
    return ''


@login_required
@require_http_methods(['GET', 'POST'])
def regras_geracao_view(request, jogo):
    """Tela de edicao das Regras de Geracao de um Jogo (Story 4.3, FR-18/FR-23). Salvar grava uma
    linha por regra do Jogo (nunca deleta); so 'Restaurar padrao' apaga as linhas do user+game."""
    game = _game_from_slug(jogo)
    if game is None:
        raise Http404('Jogo inexistente.')

    user_rules = GenerationRule.objects.filter(user=request.user, game=game)

    if request.method == 'POST':
        if 'restaurar' in request.POST:
            user_rules.delete()
            messages.success(request, f'Regras de {GAMES_CONFIG[game]["name"]} restauradas para o padrão do sistema.')
            return redirect('generation_rules', jogo=jogo)

        saved_by_name = {rule.rule_name: rule for rule in user_rules}
        rows, has_errors = _build_rule_rows(game, saved_by_name, posted=request.POST)
        if not has_errors:
            with transaction.atomic():  # tudo ou nada: nunca um conjunto de regras salvo pela metade
                for row in rows:
                    defaults = {'enabled': row['enabled']}
                    if row['enabled']:
                        if row['kind'] == 'int':
                            defaults.update(numeric_value=int(row['submitted_value']), choice_value=None)
                        else:
                            defaults.update(choice_value=row['submitted_value'], numeric_value=None)
                    # Desligada: nao toca nos valores -- preserva o que estava salvo.
                    GenerationRule.objects.update_or_create(
                        user=request.user, game=game, rule_name=row['rule_name'], defaults=defaults,
                    )
            messages.success(
                request,
                f'Regras de {GAMES_CONFIG[game]["name"]} salvas. Valem a partir do próximo jogo gerado.',
            )
            return redirect('generation_rules', jogo=jogo)
        messages.error(request, 'Corrija os campos destacados para salvar as regras.')
    else:
        saved_by_name = {rule.rule_name: rule for rule in user_rules}
        rows, has_errors = _build_rule_rows(game, saved_by_name)

    context = {
        'game_key': game,
        'game_name': GAMES_CONFIG[game]['name'],
        'rows': rows,
        'is_customized': user_rules.exists(),
        'requires_sequence_protection': game in GAMES_WITH_SEQUENCE_RULE,
        'sequence_rule_names': SEQUENCE_RULE_NAMES,
    }
    return render(request, 'loterias_core/regras_geracao.html', context)
