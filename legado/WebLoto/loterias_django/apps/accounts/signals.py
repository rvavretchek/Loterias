from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import User


@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    """Envia e-mail de boas-vindas apos criacao do usuario."""
    if created and instance.email:
        subject = 'Bem-vindo ao Gerador de Loterias!'
        message = (
            f"Olá {instance.first_name or 'Usuário'},\n\n"
            f"Seja bem-vindo ao Gerador de Loterias! Sua conta foi criada com sucesso.\n\n"
            f"Agora você pode:\n"
            f"- Gerar apostas para diversas loterias brasileiras\n"
            f"- Manter um histórico completo dos seus jogos\n"
            f"- Acompanhar estatísticas e padrões\n\n"
            f"Acesse agora: http://localhost:8000\n\n"
            f"Atenciosamente,\n"
            f"Equipe Gerador de Loterias"
        )
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [instance.email],
                fail_silently=True,
            )
        except Exception:
            pass
