import logging

from .models import GeneratedBet, HitNotification, LotteryResult
from .utils import apply_prize_to_bet, calculate_bet_prize, fetch_cef_result

logger = logging.getLogger(__name__)


def fetch_daily_results(final=False):
    """Captura resultados oficiais pendentes e gera notificacao de acerto (rotina de cron,
    Stories 2.1 e 2.3).

    `final` ainda nao muda nenhum comportamento nesta story -- e consumido
    pela Story 2.9 (alerta ao operador quando a ultima tentativa do dia
    ainda falhar pra um par Jogo/Concurso).
    """
    existing_results = set(LotteryResult.objects.values_list('game', 'contest'))
    all_bet_pairs = set(GeneratedBet.objects.values_list('game', 'contest').distinct())
    open_pairs = all_bet_pairs - existing_results

    resolved = 0
    for game, contest in open_pairs:
        try:
            result = fetch_cef_result(game, contest)
            if not result:
                logger.info('fetch_daily_results: sem resultado disponivel para %s/%s', game, contest)
                continue
            LotteryResult.objects.update_or_create(
                game=game,
                contest=contest,
                defaults={
                    'numbers': result.get('numbers', []),
                    'clovers': result.get('clovers', []),
                    'prizes': result.get('prizes', {}),
                    'source': 'CEF',
                }
            )
            resolved += 1
        except Exception:
            logger.exception('fetch_daily_results: falha ao capturar/gravar resultado para %s/%s', game, contest)
            continue

    logger.info(
        'fetch_daily_results: captura concluida (final=%s) -- %d/%d pares resolvidos',
        final, resolved, len(open_pairs),
    )

    notified = _notify_covered_bets()
    logger.info('fetch_daily_results: varredura de notificacao concluida -- %d notificacoes novas', notified)

    return True


def _notify_covered_bets():
    """Varredura por estado (AD-4, Story 2.3): todo GeneratedBet ainda sem HitNotification cujo
    Jogo+Concurso ja tem LotteryResult (gravado agora ou antes, por qualquer caminho) ganha os
    campos-cache atualizados e, se houve interseccao (hits > 0) OU premio real (won -- cobre a
    Lotomania, que paga por 0 acertos), uma HitNotification. Nunca usar so `hits > 0` aqui: isso
    excluiria justamente o unico caso em que 0 acertos e um premio de verdade."""
    candidates = GeneratedBet.objects.filter(notification__isnull=True)
    results_by_pair = {
        (r.game, r.contest): r
        for r in LotteryResult.objects.filter(
            game__in=candidates.values_list('game', flat=True),
            contest__in=candidates.values_list('contest', flat=True),
        )
    }

    notified = 0
    for bet in candidates:
        try:
            result = results_by_pair.get((bet.game, bet.contest))
            if not result:
                continue
            official_result = {
                'numbers': result.numbers,
                'clovers': result.clovers,
                'prizes': result.prizes,
            }
            prize = calculate_bet_prize(bet.game, bet.numbers, bet.clovers, official_result)
            apply_prize_to_bet(bet, prize)
            if prize['hits'] > 0 or prize['won']:
                _, created = HitNotification.objects.get_or_create(bet=bet, defaults={'won': prize['won']})
                if created:
                    notified += 1
        except Exception:
            logger.exception('fetch_daily_results: falha ao processar o bet %s pra notificacao', bet.pk)
            continue
    return notified
