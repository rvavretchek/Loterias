import random
import re
from decimal import Decimal

import requests

from .models import GeneratedBet, LotteryResult, GAMES_CONFIG, GAMES_WITH_SEQUENCE_RULE, MIN_SEQUENCE_INTERVAL


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


def calculate_bet_prize(game, user_numbers, user_clovers=None, official_result=None):
    """Compara o jogo do usuario com o resultado oficial da CEF e informa premio, acertos e status."""
    if official_result is None:
        return {'won': False, 'hits': 0, 'value': 'R$ 0,00', 'category': 'Sem resultado'}

    user_numbers = set(normalize_numbers(user_numbers))
    result_numbers = set(normalize_numbers(official_result.get('numbers', [])))
    hits = len(user_numbers & result_numbers)

    prizes = official_result.get('prizes', {})
    prize_key = None
    amount = Decimal('0')

    if game == 'Mega-sena':
        prize_key = 'sena' if hits >= 4 else None
    elif game == 'Quina':
        prize_key = 'quina' if hits >= 3 else None
    elif game == 'Lotofacil':
        prize_key = 'lotofacil' if hits >= 11 else None
    elif game == 'Lotomania':
        prize_key = 'lotomania' if hits >= 0 else 'lotomania'
    elif game == 'Milionaria':
        prize_key = 'milionaria' if hits >= 4 else None
    elif game == 'Dupla-Sena':
        prize_key = 'dupla_sena' if hits >= 4 else None

    if prize_key and isinstance(prizes, dict):
        prize_info = prizes.get(str(hits), {})
        raw_amount = prize_info.get('value', 'R$ 0,00')
        raw_amount = str(raw_amount).replace('R$', '').replace('.', '').replace(',', '.')
        try:
            amount = Decimal(raw_amount.strip())
        except Exception:
            amount = Decimal('0')

    won = bool(prize_key and hits > 0 and amount > 0)
    return {
        'won': won,
        'hits': hits,
        'value': f'R$ {amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
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
        bet.result_checked = True
        bet.hits = prize['hits']
        bet.prize = Decimal(str(prize['value'].replace('R$ ', '').replace('.', '').replace(',', '.')))
        bet.prize_description = prize['category']
        bet.save(update_fields=['result_checked', 'hits', 'prize', 'prize_description', 'updated_at'])

    return True
