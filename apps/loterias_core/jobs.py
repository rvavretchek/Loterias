import logging

from .models import GeneratedBet, LotteryResult
from .utils import fetch_cef_result

logger = logging.getLogger(__name__)


def fetch_daily_results(final=False):
    """Captura resultados oficiais pendentes (rotina de cron, Story 2.1).

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
        'fetch_daily_results: execucao concluida (final=%s) -- %d/%d pares resolvidos',
        final, resolved, len(open_pairs),
    )
    return True
