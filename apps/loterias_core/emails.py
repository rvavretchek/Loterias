import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils.formats import number_format

from .models import CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS

logger = logging.getLogger(__name__)


def send_hit_notification_email(notification):
    """Envia e-mail de acerto premiado (Story 2.7). Mesmo padrao de
    apps.accounts.signals.send_welcome_email -- texto simples, fail_silently, falha isolada.
    A funcao inteira (montagem da mensagem inclusa, nao so o send_mail) fica dentro do
    try/except: um erro de formatacao nao pode derrubar a notificacao ja persistida no banco."""
    try:
        bet = notification.bet
        user = bet.user
        if not user.email:
            return

        subject = f'Você ganhou! {bet.game} - Concurso {bet.contest}'
        prize_value = number_format(bet.prize, decimal_pos=2)
        message = (
            f"Olá {user.first_name or user.email},\n\n"
            f"Seu jogo de {bet.game} (concurso {bet.contest}) foi premiado!\n\n"
            f"Acertos: {bet.hits}\n"
            f"Categoria: {bet.prize_description}\n"
            f"Valor do prêmio: R$ {prize_value}\n\n"
            f"Acesse o site para ver os detalhes completos.\n\n"
            f"Atenciosamente,\n"
            f"Equipe Gerador de Loterias"
        )

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
    except Exception:
        logger.exception(
            'send_hit_notification_email: falha ao enviar e-mail pra notificacao %s', notification.pk
        )


def send_capture_failure_alert(game, contest):
    """Avisa o operador (Boss) que a captura do resultado oficial de um par Jogo/Concurso
    continua falhando ha CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS dias ou mais (Story 2.9).

    Retorna True somente se o e-mail foi de fato despachado, False em qualquer outro caso
    (OPERATOR_ALERT_EMAIL vazio, ou falha no envio) -- isso e o que permite jobs.py so gravar
    CaptureFailureAlert (marcando "ja alertei esse par pra sempre") depois de uma entrega real,
    nunca antes: gravar incondicionalmente faria uma env var esquecida ou uma falha transiente de
    SMTP silenciar o alerta daquele par pra sempre, mesmo depois de corrigido.

    O guard de OPERATOR_ALERT_EMAIL vazio fica fora do try/except (nao pode levantar excecao);
    a partir da montagem da mensagem em diante, tudo fica dentro -- mesmo padrao fail-soft de
    send_hit_notification_email pra essa parte."""
    operator_email = getattr(settings, 'OPERATOR_ALERT_EMAIL', '')
    if not operator_email:
        logger.warning(
            'send_capture_failure_alert: OPERATOR_ALERT_EMAIL nao configurado -- alerta de %s/%s nao enviado',
            game, contest,
        )
        return False

    try:
        subject = f'[Loterias] Falha na captura do resultado -- {game} Concurso {contest}'
        message = (
            f'A captura do resultado oficial de {game}, concurso {contest}, continua sem sucesso '
            f'ha pelo menos {CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS} dias, mesmo apos as tentativas '
            f'automaticas diarias (3h, 3h15 e 3h30).\n\n'
            f'Verifique a disponibilidade da API oficial da Caixa e os logs do container de cron.'
        )
        sent_count = send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [operator_email],
            fail_silently=True,
        )
        return bool(sent_count)
    except Exception:
        logger.exception(
            'send_capture_failure_alert: falha ao enviar alerta pra %s/%s', game, contest
        )
        return False
