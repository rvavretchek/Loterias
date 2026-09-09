from django import forms

from .models import NotificationPreference


class NotificationPreferenceForm(forms.ModelForm):
    """Formulario de preferencia de canal de aviso de acerto. A validacao de "pelo menos 1
    canal ativo" vive em NotificationPreference.clean() (model), nao aqui -- assim tambem se
    aplica ao form automatico do Django admin, sem duplicar a regra em 2 lugares."""

    class Meta:
        model = NotificationPreference
        fields = ['site_enabled', 'email_enabled']
        widgets = {
            'site_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
