from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


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

    def save_user(self, request, user, form, commit=True):
        """Salva o usuario com dados adicionais."""
        user = super().save_user(request, user, form, commit=False)
        data = form.cleaned_data
        user.first_name = data.get('first_name', '')
        user.last_name = data.get('last_name', '')
        if commit:
            user.save()
        return user
