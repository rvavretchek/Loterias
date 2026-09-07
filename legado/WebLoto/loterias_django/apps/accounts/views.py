from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.views.generic import UpdateView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from allauth.account.views import SignupView
from .models import User
from .forms import CustomSignupForm, ProfileUpdateForm


class CustomSignupView(SignupView):
    form_class = CustomSignupForm
    template_name = 'accounts/signup.html'


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """View de atualizacao de perfil."""
    model = User
    form_class = ProfileUpdateForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('profile')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, 'Perfil atualizado com sucesso!')
        return super().form_valid(form)


def toggle_theme(request):
    """Alterna entre tema claro e escuro."""
    if request.user.is_authenticated:
        user = request.user
        user.tema_preferido = 'dark' if user.tema_preferido == 'light' else 'light'
        user.save(update_fields=['tema_preferido'])
    else:
        # Para usuarios anonimos, usar sessao
        current = request.session.get('theme', 'light')
        request.session['theme'] = 'dark' if current == 'light' else 'light'

    referer = request.META.get('HTTP_REFERER', '/')
    return redirect(referer)
