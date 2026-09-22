import random
import re
from decimal import Decimal

import requests
from django.utils import timezone

from .models import (
    GeneratedBet, LotteryResult, PrizeTier, GenerationRule, GAME_GRID,
    GAMES_CONFIG, GAMES_WITH_SEQUENCE_RULE, MIN_SEQUENCE_INTERVAL, normalize_contest,
)


def normalize_numbers(numbers):
    """Normaliza entradas em lista de inteiros para uso em validação e tabela."""
    if numbers is None:
        return []
    if isinstance(numbers, str):
        numbers = numbers.replace(' ', '').replace(';', ',').replace('.', ',')
        if ',' in numbers:
            parts = numbers.split(',')
        else:
            parts = [numbers]
        return [int(item) for item in parts if item]
    if isinstance(numbers, (list, tuple, set)):
        return [int(item) for item in numbers]
    return [int(numbers)]


def count_sequential_pairs(numbers):
    """Conta quantos pares de numeros consecutivos existem na lista ordenada."""
    if len(numbers) < 2:
        return 0
    pairs = 0
    i = 0
    nums_sorted = sorted(numbers)
    while i < len(nums_sorted) - 1:
        if nums_sorted[i + 1] == nums_sorted[i] + 1:
            pairs += 1
            i += 2
        else:
            i += 1
    return pairs


def recent_bets_had_sequence(user, game_name, interval=MIN_SEQUENCE_INTERVAL):
    """Verifica se nos ultimos N jogos do mesmo tipo houve algum par sequencial."""
    recent_bets = GeneratedBet.objects.filter(
        user=user,
        game=game_name
    ).order_by('-created_at')[:interval]

    for bet in recent_bets:
        if count_sequential_pairs(bet.numbers) > 0:
            return True
    return False


def _sequence_run_lengths(numbers):
    """Tamanhos dos 'runs' (blocos de numeros consecutivos) de 2 ou mais, na lista ordenada."""
    runs = []
    current = 1
    ordered = sorted(numbers)
    for previous, following in zip(ordered, ordered[1:]):
        if following == previous + 1:
            current += 1
        else:
            if current >= 2:
                runs.append(current)
            current = 1
    if current >= 2:
        runs.append(current)
    return runs


def _distribution_bands(config, game=None):
    """Faixas da Distribuicao Homogenea: lista de (inicio, fim, quota) inclusivos.
    Padrao: bets_count faixas de largura igual (a ultima absorve o resto), 1 numero cada. Quando isso
    daria faixas de 1 numero (Lotofacil, 15 de 25), usa uma faixa por linha do volante com
    bets_count // linhas numeros em cada (3 por linha). Sem esquema aplicavel, retorna []."""
    count = config['bets_count']
    total = config['numbers_count']
    width = total // count if count else 0
    if width >= 2:
        return [
            (index * width + 1, (index + 1) * width if index < count - 1 else total, 1)
            for index in range(count)
        ]
    grid = GAME_GRID.get(game or config['name'])
    if not grid or not grid[0] or count % grid[0]:
        return []
    rows, cols = grid
    return [(row * cols + 1, (row + 1) * cols, count // rows) for row in range(rows)]


def _sequence_spans(numbers):
    """Blocos (inicio, fim) de 2+ numeros consecutivos, na lista ordenada."""
    spans = []
    ordered = sorted(numbers)
    start = None
    for previous, following in zip(ordered, ordered[1:]):
        if following == previous + 1:
            if start is None:
                start = previous
        elif start is not None:
            spans.append((start, previous))
            start = None
    if start is not None:
        spans.append((start, ordered[-1]))
    return spans


def bet_satisfies_rules(numbers, clovers, game, rules):
    """Checa um candidato contra as Regras de Geracao (AD-12). Funcao pura, sem I/O. Retorna
    (ok, violated_rule_names) com a lista COMPLETA de regras violadas. Ignora regra desligada, sem
    valor ou desconhecida."""
    violated = []
    config = GAMES_CONFIG.get(game)
    grid = GAME_GRID.get(game)
    ordered = sorted(numbers)

    for rule in rules:
        if not rule.enabled:
            continue
        name = rule.rule_name
        value = rule.numeric_value

        if name == 'limit_sequence_count':
            if value is None:
                continue
            runs = _sequence_run_lengths(ordered)
            longest = max(runs) if runs else 1
            if longest > value:
                violated.append(name)
        elif name == 'limit_sequence_pairs':
            if value is None:
                continue
            if len(_sequence_run_lengths(ordered)) > value:
                violated.append(name)
        elif name in ('limit_row_count', 'limit_column_count'):
            if value is None or grid is None:
                continue
            cols = grid[1]
            counts = {}
            for n in ordered:
                key = (n - 1) // cols + 1 if name == 'limit_row_count' else (n - 1) % cols + 1
                counts[key] = counts.get(key, 0) + 1
            if counts and max(counts.values()) > value:
                violated.append(name)
        elif name == 'distribution_type':
            if rule.choice_value != 'homogenea' or config is None:
                continue
            for start, end, quota in _distribution_bands(config, game):  # sem faixas = nao se aplica
                if sum(1 for n in ordered if start <= n <= end) != quota:
                    violated.append(name)
                    break
        elif name == 'limit_min_sequences':
            if value is None:
                continue
            if len(_sequence_spans(ordered)) < value:
                violated.append(name)
        elif name == 'limit_min_gap_between_sequences':
            if value is None:
                continue
            spans = _sequence_spans(ordered)
            if any(nxt[0] - prev[1] - 1 < value for prev, nxt in zip(spans, spans[1:])):
                violated.append(name)
    return (not violated), violated


def _random_numbers(config, homogeneous=False, game=None):
    if homogeneous:
        numbers = []
        for start, end, quota in _distribution_bands(config, game):
            numbers.extend(random.sample(range(start, end + 1), quota))
        return sorted(numbers)
    numbers = []
    while len(numbers) < config['bets_count']:
        number = random.randint(1, config['numbers_count'])
        if number not in numbers:
            numbers.append(number)
    return sorted(numbers)


def _random_clovers(config):
    clovers = []
    if config['clovers_count'] > 0:
        while len(clovers) < config['clovers']:
            clover = random.randint(1, config['clovers_count'])
            if clover not in clovers:
                clovers.append(clover)
        clovers.sort()
    return clovers


def generate_bet(game_name, user=None):
    """Compat: gera uma aposta e devolve (numeros, trevos). Ver generate_bet_with_relaxation."""
    numbers, clovers, _relaxed = generate_bet_with_relaxation(game_name, user)
    return numbers, clovers


def _draw_with_rules(config, game_name, active_rules, attempts=10000):
    """Sorteia ate `attempts` candidatos contra `active_rules`. Retorna (numeros|None, violadas do
    ultimo candidato)."""
    homogeneous = bool(_distribution_bands(config, game_name)) and any(
        rule.rule_name == 'distribution_type' and rule.choice_value == 'homogenea'
        for rule in active_rules
    )
    violated = []
    for _ in range(attempts):
        candidate = _random_numbers(config, homogeneous, game_name)
        ok, violated = bet_satisfies_rules(candidate, [], game_name, active_rules)
        if ok:
            return candidate, []
    return None, violated


def generate_bet_with_relaxation(game_name, user=None):
    """Gera uma aposta valida e devolve (numeros, trevos, regra_relaxada).

    Sem personalizacao salva (ou user None): Regra de Sequencia adaptativa (regra_relaxada=None).
    Com linhas GenerationRule do user+game (mesmo todas desligadas): so as regras ligadas valem e a
    adaptativa nao e consultada (Story 4.4). Se nada valido sai em 10000 tentativas, relaxa UMA regra
    (Story 4.5, FR-22/AD-12): a de maior updated_at entre as que o ULTIMO candidato violou, so em
    memoria, e tenta mais 10000 vezes; se ainda falhar devolve (None, None, None)."""
    config = GAMES_CONFIG.get(game_name)
    if not config:
        return None, None, None

    if user is not None and getattr(user, 'is_authenticated', True):
        user_rules = GenerationRule.objects.filter(user=user, game=game_name)
        has_customization = user_rules.exists()
    else:
        has_customization = False

    if has_customization:
        active_rules = list(user_rules.filter(enabled=True))
        candidate, violated = _draw_with_rules(config, game_name, active_rules)
        relaxed = None
        if candidate is None and violated:
            blocking = [rule for rule in active_rules if rule.rule_name in violated]
            relaxed_rule = max(blocking, key=lambda rule: (rule.updated_at, rule.pk))
            relaxed = relaxed_rule.rule_name
            reduced = [rule for rule in active_rules if rule is not relaxed_rule]
            candidate, _violated = _draw_with_rules(config, game_name, reduced)
        if candidate is None:
            return None, None, None
        return candidate, _random_clovers(config), relaxed

    applies_sequence_rule = game_name in GAMES_WITH_SEQUENCE_RULE

    if applies_sequence_rule and user is not None:
        block_sequences = recent_bets_had_sequence(user, game_name)
    else:
        block_sequences = False

    max_attempts = 10000
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        bet_numbers = []
        while len(bet_numbers) < config['bets_count']:
            number = random.randint(1, config['numbers_count'])
            if number not in bet_numbers:
                bet_numbers.append(number)

        bet_numbers.sort()

        if applies_sequence_rule:
            pairs = count_sequential_pairs(bet_numbers)

            if block_sequences:
                if pairs > 0:
                    continue
            else:
                if pairs > 1:
                    continue

        break

    bet_clovers = []
    if config['clovers_count'] > 0:
        while len(bet_clovers) < config['clovers']:
            clover = random.randint(1, config['clovers_count'])
            if clover not in bet_clovers:
                bet_clovers.append(clover)
        bet_clovers.sort()

    return bet_numbers, bet_clovers, None


def check_duplicate_bet(user, game_name, numbers, clovers):
    """Verifica se um jogo identico ja foi gerado pelo usuario."""
    return GeneratedBet.objects.filter(
        user=user,
        game=game_name,
        numbers=numbers,
        clovers=clovers if clovers else []
    ).exists()


def suggest_next_contest(game_name):
    """Sugere o proximo numero de concurso pro Jogo, a partir do maior concurso numerico ja
    conhecido em LotteryResult (+1). Desde a Story 2.12, todo concurso valido e numerico (nao existe
    concurso genuinamente alfanumerico -- ate um especial/comemorativo tem numero ordinario na CEF);
    o parse defensivo abaixo so ignora entrada nao numerica que porventura exista em dado legado.
    Retorna None se nao houver nenhum LotteryResult conhecido pro Jogo ainda."""
    known_contests = []
    for contest in LotteryResult.objects.filter(game=game_name).values_list('contest', flat=True):
        try:
            known_contests.append(int(contest))
        except (TypeError, ValueError):
            continue
    if not known_contests:
        return None
    return str(max(known_contests) + 1)


def calculate_statistics(user, game_name):
    """Calcula estatisticas para um tipo de jogo especifico."""
    bets = GeneratedBet.objects.filter(user=user, game=game_name)
    total = bets.count()

    if total == 0:
        return None

    with_sequence = bets.filter(sequential_pairs__gt=0).count()

    frequency = {}
    for bet in bets:
        for num in bet.numbers:
            frequency[num] = frequency.get(num, 0) + 1

    most_frequent = sorted(frequency.items(), key=lambda x: x[1], reverse=True)[:10]

    sequence_percentage = (with_sequence / total * 100) if total > 0 else 0
    return {
        'total': total,
        'with_sequence': with_sequence,
        'without_sequence': total - with_sequence,
        'most_frequent': most_frequent,
        'sequence_percentage': sequence_percentage,
        'without_sequence_percentage': 100 - sequence_percentage,
    }


GAME_PRIZE_CATEGORY = {
    'Mega-sena': 'sena',
    'Quina': 'quina',
    'Lotofacil': 'lotofacil',
    'Lotomania': 'lotomania',
    'Milionaria': 'milionaria',
    'Dupla-Sena': 'dupla_sena',
}

LEGACY_MIN_HITS = {
    'Mega-sena': 4,
    'Quina': 3,
    'Lotofacil': 11,
    'Milionaria': 4,
    'Dupla-Sena': 4,
}


def _parse_currency(raw_value):
    raw_value = str(raw_value).replace('R$', '').replace('.', '').replace(',', '.')
    try:
        return Decimal(raw_value.strip())
    except Exception:
        return Decimal('0')


def _legacy_hits_is_valid(game, hits):
    """Comportamento anterior a Story 2.8, preservado como fallback de cold-start (ver
    calculate_bet_prize): a Lotomania sempre foi tratada como potencialmente valida pra
    qualquer quantidade de acertos (o valor real da faixa e quem decide `won`)."""
    if game == 'Lotomania':
        return True
    min_hits = LEGACY_MIN_HITS.get(game)
    return min_hits is not None and hits >= min_hits


def _find_prize_tier(game, hits, reference_month):
    return PrizeTier.objects.filter(
        game=game, hits=hits, reference_month__lte=reference_month
    ).order_by('-reference_month').first()


def _reference_month_for(captured_at):
    """Converte um `captured_at` (aware ou None) no primeiro dia do mes correspondente, no fuso
    local (America/Sao_Paulo) -- nao em UTC. `timezone.now()`/`DateTimeField.auto_now_add` guardam
    o instante em UTC quando USE_TZ=True; chamar `.date()` direto nele pega a data UTC, que pode
    cair no dia (e mes) seguinte ao horario local perto da meia-noite de Brasilia."""
    if captured_at is None:
        return timezone.localdate().replace(day=1)
    if hasattr(captured_at, 'date'):
        if timezone.is_aware(captured_at):
            captured_at = timezone.localtime(captured_at)
        return captured_at.date().replace(day=1)
    return captured_at.replace(day=1)


def calculate_bet_prize(game, user_numbers, user_clovers=None, official_result=None):
    """Compara o jogo do usuario com o resultado oficial da CEF e informa premio, acertos e
    status. A validade de uma quantidade de acertos e decidida nesta ordem de prioridade:

    1. A propria faixa de premiacao do concurso (`prizes` do LotteryResult daquele Jogo+Concurso
       especifico) -- e um dado real e definitivo daquele sorteio, e o LotteryResult nunca e
       podado (AD-10). Uma aposta antiga genuinamente premiada nao pode perder o reconhecimento
       do premio so porque a retencao de 3 meses do PrizeTier (Story 2.8/AD-10) ja descartou o
       reference_month dela -- o dado do proprio concurso e a fonte da verdade.
    2. PrizeTier (Story 2.8/AD-10), usado so quando o concurso especifico nao tem essa faixa
       registrada (ex.: captura incompleta daquele concurso).
    3. O fallback legado hardcoded (_legacy_hits_is_valid), usado so em cold-start total
       (nenhum PrizeTier pro Jogo ainda, ver jobs.fetch_daily_results)."""
    if official_result is None:
        return {'won': False, 'hits': 0, 'value': 'R$ 0,00', 'category': 'Sem resultado'}

    reference_month = _reference_month_for(official_result.get('captured_at'))
    result = _calculate_prize_for_draw(
        game, user_numbers, official_result.get('numbers', []),
        official_result.get('prizes', {}), reference_month,
    )

    # Story 2.18: Dupla-Sena tem 2 sorteios por concurso -- confere o jogo do usuario contra os 2
    # separadamente e fica com o de maior premio (nunca soma os 2, nunca ignora o 2o sorteio).
    if game == 'Dupla-Sena' and official_result.get('numbers_second_draw'):
        second_draw_result = _calculate_prize_for_draw(
            game, user_numbers, official_result['numbers_second_draw'],
            official_result.get('prizes_second_draw', {}), reference_month,
        )
        if _parse_currency(second_draw_result['value']) > _parse_currency(result['value']):
            result = second_draw_result
            result['draw'] = 2

    # Trevos da +Milionaria: so pra exibir a comparacao (nao entram no calculo do premio).
    result['matched_clovers'] = sorted(
        set(normalize_numbers(user_clovers or [])) & set(normalize_numbers(official_result.get('clovers') or []))
    )
    result['result'] = official_result
    return result


def _calculate_prize_for_draw(game, user_numbers, draw_numbers, prizes, reference_month):
    """Nucleo de calculate_bet_prize pra UM sorteio -- extraido na Story 2.18 pra permitir a
    Dupla-Sena chamar isso 2x (1 por sorteio) e comparar qual rendeu mais premio, sem duplicar a
    logica de prioridade (concurso especifico > PrizeTier > fallback legado)."""
    user_numbers_set = set(normalize_numbers(user_numbers))
    result_numbers = set(normalize_numbers(draw_numbers))
    hits = len(user_numbers_set & result_numbers)

    concurso_prize_info = prizes.get(str(hits)) if isinstance(prizes, dict) else None
    tier = _find_prize_tier(game, hits, reference_month)

    if concurso_prize_info is not None:
        is_valid = True
    elif tier is not None:
        is_valid = True
    elif PrizeTier.objects.filter(game=game).exists():
        is_valid = False
    else:
        is_valid = _legacy_hits_is_valid(game, hits)

    amount = Decimal('0')
    if is_valid:
        if concurso_prize_info is not None:
            amount = _parse_currency(concurso_prize_info.get('value', 'R$ 0,00'))
        elif tier is not None:
            amount = tier.value

    prize_key = GAME_PRIZE_CATEGORY.get(game) if is_valid else None
    won = bool(is_valid and amount > 0)
    return {
        'won': won,
        'hits': hits,
        'value': _format_currency(amount),
        'category': prize_key or 'Sem premio',
        'matched_numbers': sorted(user_numbers_set & result_numbers),
        'draw': 1,
    }


PRIZE_TIER_PATTERN = re.compile(r'^(\d+) acertos$')


def _format_currency(value):
    return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _extract_prize_tiers(tiers):
    """Converte a lista de faixas (`listaRateioPremio` da API oficial) num dict {"acertos": {value, winners}}
    (chave string -- `prizes` e um JSONField, e JSON so tem chave string; usar int aqui quebraria
    silenciosamente a leitura de volta do banco), uma entrada por quantidade real de acertos -- nao so a
    faixa de acerto maximo, ja que jogos como Mega-Sena premiam quadra/quina/sena em faixas de valor bem
    diferentes.

    A Dupla-Sena tem 2 sorteios com faixas repetidas (mesma quantidade de acertos aparece 2x, uma
    por sorteio) -- esta funcao sempre fica com a primeira ocorrencia. `fetch_cef_result` (Story
    2.18) usa essa propriedade a seu favor: chama esta funcao 1x sobre a lista inteira (extrai so
    o 1o sorteio, dedup natural) e 1x sobre so a segunda metade (extrai o 2o sorteio a parte).
    Importante pra essa dedup: uma faixa SEMPRE reserva `hits_key` em `result` na primeira
    ocorrencia que casar o regex (mesmo quando `winners` fica None por falha de extracao, ver
    abaixo) -- nunca "pula" a faixa inteira, senao uma ocorrencia posterior tomaria o lugar da 1a.

    `winners` vira None (Story 2.11) quando a faixa tem valor de premio positivo mas a API nao
    informou a quantidade de ganhadores (None, nao simplesmente 0) -- e tratado como falha de
    extracao SO daquele campo, nao fabrica um "0" que pareceria um concurso acumulado legitimo.
    O `value` (que veio correto da API) e sempre preservado nesse caso -- descartar a faixa
    inteira jogaria fora justamente o dado usado por calculate_bet_prize pra decidir o premio
    (que nunca le `winners`), negando ou subestimando um premio real por causa de um campo que
    nem influencia esse calculo. Uma faixa genuinamente sem premio (valor E ganhadores
    zerados/ausentes, ex. concurso acumulado) continua sendo extraida normalmente com winners=0.
    Um `valorPremio` negativo ou de tipo invalido descarta a faixa (dado corrompido, sem uso)."""
    result = {}
    for tier in tiers or []:
        match = PRIZE_TIER_PATTERN.match(tier.get('descricaoFaixa') or '')
        if not match:
            continue
        hits_key = match.group(1)
        if hits_key in result:
            continue
        try:
            raw_value = float(tier.get('valorPremio') or 0)
        except (TypeError, ValueError):
            continue
        if raw_value < 0:
            continue
        raw_winners = tier.get('numeroDeGanhadores')
        winners = None if (raw_value and raw_winners is None) else (raw_winners or 0)
        result[hits_key] = {
            'value': _format_currency(raw_value),
            'winners': winners,
        }
    return result


def fetch_cef_result(game, contest):
    """Busca o resultado oficial do jogo e concurso na API oficial da CEF
    (`servicebus2.caixa.gov.br/portaldeloterias/api`). Se a API estiver indisponivel, ou o concurso
    devolvido nao bater com o pedido, retorna None -- nunca aceita um resultado de outro concurso.

    Story 2.18: Dupla-Sena tem 2 sorteios por concurso. `listaRateioPremio` traz as faixas dos 2
    sorteios concatenadas (1o sorteio primeiro, mesmas quantidades de acertos repetidas pro 2o) --
    `_extract_prize_tiers` sobre a lista inteira ja extrai só o 1o sorteio (dedup por chave mantem
    a 1a ocorrencia); a segunda metade da lista e extraida separadamente pro 2o sorteio. Os 2
    campos de 2o sorteio ficam sempre presentes no dict devolvido (vazios pra qualquer jogo que nao
    seja Dupla-Sena, ou se a API nao trouxer o 2o sorteio), pra chamadores nao precisarem checar
    `game == 'Dupla-Sena'` toda vez."""
    game_slug = {
        'Mega-sena': 'megasena',
        'Milionaria': 'maismilionaria',
        'Lotomania': 'lotomania',
        'Lotofacil': 'lotofacil',
        'Quina': 'quina',
        'Dupla-Sena': 'duplasena',
    }.get(game)

    if not game_slug:
        return None

    url = f'https://servicebus2.caixa.gov.br/portaldeloterias/api/{game_slug}/{contest}'
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None

        if int(data.get('numero')) != int(contest):
            return None

        numbers = [int(n) for n in data.get('listaDezenas') or []]
        if not numbers:
            return None
        clovers = [int(t) for t in data.get('trevosSorteados') or []]
        raw_tiers = data.get('listaRateioPremio') or []
        prizes = _extract_prize_tiers(raw_tiers)

        numbers_second_draw = []
        prizes_second_draw = {}
        if game == 'Dupla-Sena':
            numbers_second_draw = [int(n) for n in data.get('listaDezenasSegundoSorteio') or []]
            if numbers_second_draw and len(raw_tiers) % 2 == 0:
                # so divide a lista ao meio quando o total e par (estrutura conhecida: N faixas do
                # 1o sorteio + N faixas identicas do 2o) -- uma contagem impar indicaria formato
                # inesperado da API, e adivinhar o corte arriscaria atribuir a faixa errada ao
                # sorteio errado. Nesse caso raro, prizes_second_draw fica vazio (numbers_second_draw
                # ainda e capturado) em vez de um split as-cegas.
                prizes_second_draw = _extract_prize_tiers(raw_tiers[len(raw_tiers) // 2:])
    except Exception:
        return None

    return {
        'game': game,
        'contest': contest,
        'numbers': numbers,
        'clovers': clovers,
        'prizes': prizes,
        'numbers_second_draw': numbers_second_draw,
        'prizes_second_draw': prizes_second_draw,
    }


def apply_prize_to_bet(bet, prize):
    """Aplica o retorno de calculate_bet_prize aos campos-cache do GeneratedBet e salva."""
    bet.result_checked = True
    bet.hits = prize['hits']
    bet.prize = _parse_currency(prize['value'])
    bet.prize_description = prize['category']
    bet.save(update_fields=['result_checked', 'hits', 'prize', 'prize_description', 'updated_at'])


def check_user_results(user=None):
    """Valida jogos do usuario contra resultados oficiais da CEF e atualiza o status de premio."""
    queryset = GeneratedBet.objects.all()
    if user is not None:
        queryset = queryset.filter(user=user)

    for bet in queryset:
        if bet.result_checked:
            continue
        result = fetch_cef_result(bet.game, bet.contest)
        if not result:
            continue
        prize = calculate_bet_prize(bet.game, bet.numbers, bet.clovers, result)
        apply_prize_to_bet(bet, prize)

    return True
