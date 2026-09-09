from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Count
from .models import GeneratedBet, LotteryResult, GAMES_CONFIG, GAMES_WITH_SEQUENCE_RULE
from .utils import (
    generate_bet, check_duplicate_bet, count_sequential_pairs,
    calculate_statistics, normalize_numbers, calculate_bet_prize,
    fetch_cef_result, suggest_next_contest, apply_prize_to_bet
)


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

    blocked = _block_if_contest_already_drawn(request, selected_game, contest)
    if blocked:
        return blocked

    # Verificar se concurso ja existe para este usuario e jogo
    if GeneratedBet.objects.filter(user=request.user, game=selected_game, contest=contest).exists():
        messages.warning(request, f'Ja existe um jogo de {selected_game} para o concurso {contest}.')

    attempts = 0
    max_attempts = 1000
    new_bet = None
    new_clovers = None

    while attempts < max_attempts:
        nums, clovers = generate_bet(selected_game, request.user)

        if check_duplicate_bet(request.user, selected_game, nums, clovers):
            attempts += 1
            continue

        new_bet = nums
        new_clovers = clovers
        break

    if not new_bet:
        messages.warning(request, 'Nao foi possivel gerar um jogo unico apos muitas tentativas.')
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
            }
        )

    context = {
        'jogo': bet,
        'jogos_anteriores': previous_bets,
        'aplica_regra_sequencia': bet.game in GAMES_WITH_SEQUENCE_RULE,
        'resultado_oficial': official_result,
        'premio_info': prize_info,
    }

    return render(request, 'loterias_core/detalhes_jogo.html', context)


@login_required
def history_view(request):
    """Pagina de historico de jogos."""
    bets_list = GeneratedBet.objects.filter(user=request.user)

    game_filter = request.GET.get('jogo')
    if game_filter and game_filter in GAMES_CONFIG:
        bets_list = bets_list.filter(game=game_filter)

    valid_orderings = {'-created_at', 'created_at', 'game', 'contest'}
    ordering = request.GET.get('ordenacao', '-created_at')
    if ordering not in valid_orderings:
        ordering = '-created_at'
    bets_list = bets_list.order_by(ordering)

    paginator = Paginator(bets_list, 20)
    page_number = request.GET.get('page')
    bets = paginator.get_page(page_number)

    context = {
        'jogos': bets,
        'jogos_disponiveis': GAMES_CONFIG,
        'jogo_filtro': game_filter,
        'ordenacao': ordering,
    }

    return render(request, 'loterias_core/historico.html', context)


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

    if GeneratedBet.objects.filter(user=request.user, game=selected_game, contest=contest).exists():
        messages.warning(request, f'Ja existe um jogo de {selected_game} para o concurso {contest}.')

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
    """Refaz um jogo existente gerando novos numeros."""
    original_bet = get_object_or_404(GeneratedBet, pk=pk, user=request.user)

    blocked = _block_if_contest_already_drawn(request, original_bet.game, original_bet.contest, redirect_to='bet_detail', pk=pk)
    if blocked:
        return blocked

    attempts = 0
    max_attempts = 1000
    new_bet = None
    new_clovers = None

    while attempts < max_attempts:
        nums, clovers = generate_bet(original_bet.game, request.user)

        if check_duplicate_bet(request.user, original_bet.game, nums, clovers):
            attempts += 1
            continue

        new_bet = nums
        new_clovers = clovers
        break

    if not new_bet:
        messages.warning(request, 'Nao foi possivel gerar um jogo unico.')
        return redirect('bet_detail', pk=pk)

    sequential_pairs_count = count_sequential_pairs(new_bet)

    # Criar novo jogo baseado no original
    new_record = GeneratedBet.objects.create(
        user=request.user,
        game=original_bet.game,
        contest=original_bet.contest,
        numbers=new_bet,
        clovers=new_clovers if new_clovers else [],
        sequential_pairs=sequential_pairs_count
    )

    messages.success(request, f'Novo jogo de {original_bet.game} gerado com sucesso!')
    return redirect('bet_detail', pk=new_record.pk)


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

    return render(request, 'loterias_core/estatisticas.html', context)


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

    nums, clovers = generate_bet(selected_game, request.user)
    sequential_pairs_count = count_sequential_pairs(nums)

    # Verificar repeticao
    is_duplicate = check_duplicate_bet(request.user, selected_game, nums, clovers)

    return JsonResponse({
        'numeros': nums,
        'trevos': clovers,
        'pares_sequenciais': sequential_pairs_count,
        'repetido': is_duplicate,
    })
