from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from allauth.account.forms import SignupForm
from .models import User


class CustomSignupForm(SignupForm):
    """Formulario de cadastro customizado usando allauth."""
    first_name = forms.CharField(
        max_length=30, 
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Nome', 'class': 'form-control'}),
        label='Nome'
    )
    last_name = forms.CharField(
        max_length=30, 
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Sobrenome', 'class': 'form-control'}),
        label='Sobrenome'
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'seu@email.com', 'class': 'form-control'}),
        label='E-mail'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Atualizar widgets dos campos do allauth
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'seu@email.com'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Senha'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirme a senha'})

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.save()
        return user


class ProfileUpdateForm(forms.ModelForm):
    """Formulario de atualizacao de perfil."""
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'telefone', 'bio', 'avatar', 'tema_preferido')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(00) 00000-0000'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Conte um pouco sobre voce...'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
            'tema_preferido': forms.Select(attrs={'class': 'form-select'}),
        }
