import random
import re
from decimal import Decimal

import requests
from django.utils import timezone

from .models import (
    GeneratedBet, LotteryResult, PrizeTier,
    GAMES_CONFIG, GAMES_WITH_SEQUENCE_RULE, MIN_SEQUENCE_INTERVAL,
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


def generate_bet(game_name, user=None):
    """Gera uma aposta valida respeitando as regras de sequencia."""
    config = GAMES_CONFIG.get(game_name)
    if not config:
        return None, None

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

    return bet_numbers, bet_clovers


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
    conhecido em LotteryResult (+1). Concursos nao numericos (especiais/comemorativos) sao
    ignorados. Retorna None se nao houver nenhum LotteryResult conhecido pro Jogo ainda."""
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

    user_numbers = set(normalize_numbers(user_numbers))
    result_numbers = set(normalize_numbers(official_result.get('numbers', [])))
    hits = len(user_numbers & result_numbers)

    prizes = official_result.get('prizes', {})
    concurso_prize_info = prizes.get(str(hits)) if isinstance(prizes, dict) else None

    reference_month = _reference_month_for(official_result.get('captured_at'))
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
        'result': official_result,
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

    Nao resolve o caso da Dupla-Sena ter 2 sorteios com faixas repetidas (mesma quantidade de acertos
    aparece 2x, uma por sorteio) -- fica com a primeira ocorrencia (1o sorteio); extracao completa por
    sorteio e a Story 2.11."""
    result = {}
    for tier in tiers or []:
        match = PRIZE_TIER_PATTERN.match(tier.get('descricaoFaixa') or '')
        if not match:
            continue
        hits_key = match.group(1)
        if hits_key in result:
            continue
        result[hits_key] = {
            'value': _format_currency(tier.get('valorPremio') or 0),
            'winners': tier.get('numeroDeGanhadores') or 0,
        }
    return result


def fetch_cef_result(game, contest):
    """Busca o resultado oficial do jogo e concurso na API oficial da CEF
    (`servicebus2.caixa.gov.br/portaldeloterias/api`). Se a API estiver indisponivel, ou o concurso
    devolvido nao bater com o pedido, retorna None -- nunca aceita um resultado de outro concurso."""
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
        prizes = _extract_prize_tiers(data.get('listaRateioPremio') or [])
    except Exception:
        return None

    return {
        'game': game,
        'contest': contest,
        'numbers': numbers,
        'clovers': clovers,
        'prizes': prizes,
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
