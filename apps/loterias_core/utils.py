import random
import re
from decimal import Decimal

import requests

from .models import GeneratedBet, GAMES_CONFIG, GAMES_WITH_SEQUENCE_RULE, MIN_SEQUENCE_INTERVAL


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

    return {
        'total': total,
        'com_sequencia': with_sequence,
        'sem_sequencia': total - with_sequence,
        'mais_frequentes': most_frequent,
        'percentual_sequencia': (with_sequence / total * 100) if total > 0 else 0
    }


def calculate_bet_prize(game, user_numbers, user_clovers=None, official_result=None):
    """Compara o jogo do usuario com o resultado oficial da CEF e informa premio, acertos e status."""
    if official_result is None:
        return {'ganhou': False, 'acertos': 0, 'valor': 'R$ 0,00', 'categoria': 'Sem resultado'}

    user_numbers = set(normalize_numbers(user_numbers))
    result_numbers = set(normalize_numbers(official_result.get('numeros', [])))
    hits = len(user_numbers & result_numbers)

    prizes = official_result.get('premiacoes', {})
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
        prize_info = prizes.get(prize_key, {})
        raw_amount = prize_info.get('valor', 'R$ 0,00')
        raw_amount = str(raw_amount).replace('R$', '').replace('.', '').replace(',', '.')
        try:
            amount = Decimal(raw_amount.strip())
        except Exception:
            amount = Decimal('0')

    won = bool(prize_key and hits > 0 and amount > 0)
    return {
        'ganhou': won,
        'acertos': hits,
        'valor': f'R$ {amount:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
        'categoria': prize_key or 'Sem premio',
        'resultado': official_result,
    }


def fetch_cef_result(game, contest):
    """Busca o resultado oficial do jogo e concurso na CEF. Se a pagina da Caixa estiver indisponivel, retorna None."""
    game_slug = {
        'Mega-sena': 'mega-sena',
        'Milionaria': 'mais-milionaria',
        'Lotomania': 'lotomania',
        'Lotofacil': 'lotofacil',
        'Quina': 'quina',
        'Dupla-Sena': 'dupla-sena',
    }.get(game)

    if not game_slug:
        return None

    page_name = game_slug.replace('-', ' ').title().replace(' ', '-')
    url = f'https://loterias.caixa.gov.br/Paginas/{page_name}.aspx'
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
    except Exception:
        return None

    html = response.text
    block = None
    markers = [
        'Concurso', 'Sorteio', 'Concurso', 'ACUMULOU', 'GANHADOR', 'Trevos sorteados', '1º sorteio', '2º sorteio'
    ]
    for marker in markers:
        idx = html.lower().find(marker.lower())
        if idx != -1:
            block = html[idx: idx + 2500]
            break
    if not block:
        return None

    numbers = []
    for match in re.findall(r'>(\d{1,2})<', block):
        number = int(match)
        if 1 <= number <= 100:
            numbers.append(number)
    numbers = sorted(set(numbers))[:15]
    if not numbers:
        return None

    return {
        'jogo': game,
        'concurso': contest,
        'numeros': numbers,
        'trevos': [],
        'premiacoes': {'sena': {'valor': 'R$ 0,00'}}
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
        bet.hits = prize['acertos']
        bet.prize = Decimal(str(prize['valor'].replace('R$ ', '').replace('.', '').replace(',', '.')))
        bet.prize_description = prize['categoria']
        bet.save(update_fields=['result_checked', 'hits', 'prize', 'prize_description', 'updated_at'])

    return True
