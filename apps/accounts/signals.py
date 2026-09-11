from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import User


def send_welcome_email(user):
    """Envia e-mail de boas-vindas. Disparado (a) na criacao, se a conta ja nascer com senha
    usavel (createsuperuser/criacao administrativa direta -- comportamento pre-existente
    inalterado); ou (b) explicitamente quando a senha e definida pela primeira vez no novo fluxo
    de cadastro so-com-email (Story 3.1/3.3, ver InitialOrResetPasswordKeyForm.save()) -- nesses
    casos a conta nasce com senha inutilizavel, entao o post_save de criacao nao dispara sozinho."""
    if not user.email:
        return
    subject = 'Bem-vindo ao Gerador de Loterias!'
    message = (
        f"Olá {user.first_name or 'Usuário'},\n\n"
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
            [user.email],
            fail_silently=True,
        )
    except Exception:
        pass


@receiver(post_save, sender=User)
def send_welcome_email_on_creation(sender, instance, created, **kwargs):
    """So dispara na criacao se a conta ja nascer com senha usavel -- uma conta pendente (Story
    3.1, senha inutilizavel) so recebe o e-mail de boas-vindas quando de fato ativada, ver
    send_welcome_email() acima."""
    if created and instance.has_usable_password():
        send_welcome_email(instance)
