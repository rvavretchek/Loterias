from django import forms
from allauth.account.forms import ResetPasswordKeyForm, SignupForm
from .models import User


class CustomSignupForm(SignupForm):
    """Formulario de cadastro (Story 3.1) -- so o e-mail. `SignupForm.__init__` do allauth
    adiciona `password1` incondicionalmente (e `password2` conforme
    ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE) independente de ACCOUNT_SIGNUP_FIELDS -- essa setting
    so controla campos como email/username, nao senha, nesta versao do allauth. Por isso os
    campos de senha sao removidos explicitamente aqui."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('password1', 'password2'):
            self.fields.pop(field_name, None)
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'seu@email.com'})


class InitialOrResetPasswordKeyForm(ResetPasswordKeyForm):
    """Story 3.3: mesmo formulario de definicao de senha via link que o allauth ja usa pro fluxo
    de 'esqueci minha senha' -- a unica diferenca e o aceite dos termos de servico, exigido so
    quando o usuario ainda nao tem senha usavel (ou seja, e a criacao inicial da conta, nao uma
    redefinicao genuina de alguem ja ativo)."""

    terms_accepted = forms.BooleanField(
        label='Li e aceito os termos de servico',
        required=True,
        error_messages={'required': 'Voce precisa aceitar os termos de servico pra continuar.'},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # has_usable_password()==False sozinho tambem e verdade pra uma conta ja ativa que teve
        # a senha invalidada por outro motivo (ex. um admin chamando set_unusable_password() por
        # seguranca) -- exigir reaceite de termos e mandar "sua conta foi criada com sucesso" pra
        # essa pessoa seria enganoso. last_login is None so e verdade pra quem nunca terminou o
        # fluxo de login nem uma vez -- combinado, identifica a criacao inicial de verdade.
        self._is_initial_signup = (
            self.user is not None
            and not self.user.has_usable_password()
            and self.user.last_login is None
        )
        if not self._is_initial_signup:
            del self.fields['terms_accepted']
        for field_name in ('password1', 'password2'):
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({'class': 'form-control'})

    def save(self):
        super().save()
        if self._is_initial_signup:
            from .signals import send_welcome_email
            send_welcome_email(self.user)


class ProfileCompletionForm(forms.ModelForm):
    """Story 3.5: nome/sobrenome obrigatorios no primeiro login apos definir senha."""

    class Meta:
        model = User
        fields = ('first_name', 'last_name')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sobrenome'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

    def save(self, commit=True):
        user = super().save(commit=False)
        user.profile_completed = True
        if commit:
            user.save(update_fields=['first_name', 'last_name', 'profile_completed'])
        return user


class ProfileUpdateForm(forms.ModelForm):
    """Formulario de atualizacao de perfil."""
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'phone', 'bio', 'avatar', 'preferred_theme')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Conte um pouco sobre voce...'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
            'preferred_theme': forms.Select(attrs={'class': 'form-select'}),
        }
