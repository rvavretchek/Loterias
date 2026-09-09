import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils.formats import number_format

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
