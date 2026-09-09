import logging

from django.utils import timezone

from .emails import send_hit_notification_email
from .models import GeneratedBet, HitNotification, LotteryResult, NotificationPreference, PrizeTier
from .utils import GAMES_CONFIG, _parse_currency, apply_prize_to_bet, calculate_bet_prize, fetch_cef_result

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

    try:
        update_monthly_prize_values()
    except Exception:
        logger.exception('fetch_daily_results: falha ao atualizar PrizeTier (cold-start)')

    return True


def _notify_covered_bets():
    """Varredura por estado (AD-4, Story 2.3): todo GeneratedBet ainda sem HitNotification cujo
    Jogo+Concurso ja tem LotteryResult (gravado agora ou antes, por qualquer caminho) ganha os
    campos-cache atualizados e, se houve interseccao (hits > 0) OU premio real (won -- cobre a
    Lotomania, que paga por 0 acertos), uma HitNotification. Nunca usar so `hits > 0` aqui: isso
    excluiria justamente o unico caso em que 0 acertos e um premio de verdade."""
    candidates = list(GeneratedBet.objects.filter(notification__isnull=True))
    results_by_pair = {
        (r.game, r.contest): r
        for r in LotteryResult.objects.filter(
            game__in=[bet.game for bet in candidates],
            contest__in=[bet.contest for bet in candidates],
        )
    } if candidates else {}
    preferences_by_user_id = {
        p.user_id: p
        for p in NotificationPreference.objects.filter(user__in=[bet.user_id for bet in candidates])
    } if candidates else {}

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
                'captured_at': result.captured_at,
            }
            prize = calculate_bet_prize(bet.game, bet.numbers, bet.clovers, official_result)
            apply_prize_to_bet(bet, prize)
            if prize['hits'] > 0 or prize['won']:
                notification, created = HitNotification.objects.get_or_create(
                    bet=bet, defaults={'won': prize['won']}
                )
                if created:
                    notified += 1
                    if prize['won']:
                        preference = preferences_by_user_id.get(bet.user_id)
                        if preference is not None and preference.email_enabled:
                            send_hit_notification_email(notification)
        except Exception:
            logger.exception('fetch_daily_results: falha ao processar o bet %s pra notificacao', bet.pk)
            continue
    return notified


def _latest_result_for_game(game):
    """Escolhe o LotteryResult mais recente do Jogo pelo numero do concurso, nao por captured_at
    (mesmo padrao de utils.suggest_next_contest): captured_at reflete quando a linha foi gravada
    no banco, e uma verificacao manual tardia de um concurso antigo (check_bet_result_view,
    save_manual_bet_view) grava captured_at=agora nele sem esse concurso ser o mais recente de
    fato -- usar captured_at pra decidir 'o mais recente' poluiria o PrizeTier do mes com dados
    de um concurso desatualizado. Concursos nao numericos (especiais) sao ignorados."""
    numeric_results = []
    for result in LotteryResult.objects.filter(game=game):
        try:
            numeric_results.append((int(result.contest), result))
        except (TypeError, ValueError):
            continue
    if not numeric_results:
        return None
    return max(numeric_results, key=lambda pair: pair[0])[1]


def update_monthly_prize_values():
    """Captura, pra cada Jogo, uma faixa de PrizeTier por quantidade de acertos que aparece no
    LotteryResult mais recente daquele Jogo (Story 2.8/AD-10). Idempotente (update_or_create por
    game+hits+reference_month) -- seguro de chamar mais de uma vez no mesmo mes, inclusive todo
    dia dentro de fetch_daily_results (evita o mes corrente ficar sem PrizeTier ate o dia 1
    rodar pela primeira vez). Captura toda faixa presente no `prizes`, mesmo com valor/ganhadores
    zerados -- a faixa em si (ex. 'sena' da Mega-Sena) continua valida mesmo num concurso
    acumulado sem ganhador. A falha ao gravar uma faixa especifica nao impede as demais faixas do
    mesmo Jogo nem dos demais Jogos nesta execucao."""
    reference_month = timezone.localdate().replace(day=1)
    captured = 0

    for game in GAMES_CONFIG:
        try:
            latest_result = _latest_result_for_game(game)
        except Exception:
            logger.exception('update_monthly_prize_values: falha ao localizar o resultado mais recente do jogo %s', game)
            continue
        if not latest_result or not isinstance(latest_result.prizes, dict):
            continue
        for hits_key, tier_data in latest_result.prizes.items():
            try:
                hits = int(hits_key)
            except (TypeError, ValueError):
                continue
            if not isinstance(tier_data, dict):
                continue
            try:
                value = _parse_currency(tier_data.get('value', 'R$ 0,00'))
                winners = tier_data.get('winners') or 0
                PrizeTier.objects.update_or_create(
                    game=game, hits=hits, reference_month=reference_month,
                    defaults={'value': value, 'winners': winners},
                )
                captured += 1
            except Exception:
                logger.exception('update_monthly_prize_values: falha ao gravar a faixa %s do jogo %s', hits_key, game)
                continue

    _prune_old_prize_tiers()
    logger.info(
        'update_monthly_prize_values: execucao concluida -- %d faixas capturadas/atualizadas', captured
    )
    return True


def _prune_old_prize_tiers(keep=3):
    """Mantem so os `keep` reference_month mais recentes por (game, hits) -- Story 2.8/AD-10."""
    pairs = PrizeTier.objects.values_list('game', 'hits').distinct()
    for game, hits in pairs:
        months = list(
            PrizeTier.objects.filter(game=game, hits=hits)
            .order_by('-reference_month')
            .values_list('reference_month', flat=True)
        )
        stale_months = months[keep:]
        if stale_months:
            PrizeTier.objects.filter(game=game, hits=hits, reference_month__in=stale_months).delete()
