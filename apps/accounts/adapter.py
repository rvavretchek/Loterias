from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.forms import default_token_generator
from allauth.account.utils import user_pk_to_url_str
from django.conf import settings
from django.contrib import messages
from django.urls import reverse


class CustomAccountAdapter(DefaultAccountAdapter):
    """Adapter customizado para o allauth."""

    def get_email_confirmation_url(self, request, emailconfirmation):
        """Retorna a URL de confirmacao de email."""
        return f"{request.scheme}://{request.get_host()}/accounts/confirm-email/{emailconfirmation.key}/"

    def send_mail(self, template_prefix, email, context):
        """Envia email customizado."""
        context['site_name'] = 'Gerador de Loterias'
        context['support_email'] = settings.DEFAULT_FROM_EMAIL
        super().send_mail(template_prefix, email, context)

    def get_email_verification_redirect_url(self, email_address):
        """Story 3.3: confirmar o e-mail nunca loga automaticamente
        (ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION=False) -- em vez disso, redireciona pra definicao de
        senha (conta ainda pendente) reaproveitando o mesmo mecanismo de token da tela de "esqueci
        minha senha" do allauth, ou pro login com uma mensagem distinta se a conta ja tinha senha
        (vinculo clicado de novo depois de ja concluido).

        Esse hook tambem e chamado quando um usuario JA AUTENTICADO confirma um segundo e-mail
        (/accounts/email/, rota nativa do allauth, sempre ativa) -- nesse caso o comportamento
        customizado (mensagem "cadastro ja confirmado" + redirect pro login) seria uma regressao
        (o padrao do allauth so manda de volta pro get_login_redirect_url, silenciosamente,
        exatamente porque a pessoa ja esta logada e nao precisa de mensagem nenhuma). Por isso
        delegamos pro comportamento padrao quando quem confirma e o proprio usuario logado."""
        user = email_address.user
        if self.request.user.is_authenticated and self.request.user.pk == user.pk:
            return super().get_email_verification_redirect_url(email_address)
        if not user.has_usable_password():
            uidb36 = user_pk_to_url_str(user)
            key = default_token_generator.make_token(user)
            return reverse('account_reset_password_from_key', kwargs={'uidb36': uidb36, 'key': key})
        messages.info(self.request, 'Cadastro já confirmado. Faça login normalmente.')
        return reverse('account_login')
