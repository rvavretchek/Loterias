from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib import messages
from django.core.cache import cache
from django.views import View
from django.views.generic import UpdateView, FormView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.http import url_has_allowed_host_and_scheme
from allauth.account.views import SignupView
from allauth.account.utils import send_email_confirmation
from .models import User
from .forms import CustomSignupForm, ProfileCompletionForm, ProfileUpdateForm

RESEND_DAILY_LIMIT = 5
RESEND_DAILY_LIMIT_SECONDS = 24 * 60 * 60


class CustomSignupView(SignupView):
    form_class = CustomSignupForm
    template_name = 'accounts/signup.html'

    def form_valid(self, form):
        """Guarda o e-mail SUBMETIDO na sessao antes de qualquer coisa -- inclusive quando a
        conta ja existia (anti-enumeracao do allauth devolve user=None nesse caso pro adapter,
        entao capturar aqui, incondicionalmente, e o unico jeito da tela seguinte mostrar o
        e-mail certo sem vazar se a conta ja existia ou nao)."""
        self.request.session['pending_signup_email'] = form.cleaned_data['email']
        return super().form_valid(form)


class ResendConfirmationEmailView(View):
    """Story 3.2: reenvio do e-mail de confirmacao. O cooldown de 60s e aplicado nativamente pelo
    allauth (ACCOUNT_RATE_LIMITS['confirm_email']). O limite de 5/dia e implementado aqui, com
    cache key propria (nunca compartilhada com o cooldown do allauth -- ver comentario em
    settings/base.py sobre por que compartilhar a mesma acao quebra os dois limites), incrementada
    so quando um e-mail e de fato despachado."""
    http_method_names = ['post']

    def _daily_limit_cache_key(self, email):
        return f'resend-confirmation-daily:{email.lower()}'

    def post(self, request, *args, **kwargs):
        email = (request.POST.get('email') or request.session.get('pending_signup_email') or '').strip()
        if email:
            user = User.objects.filter(email__iexact=email).first()
            if user is not None:
                cache_key = self._daily_limit_cache_key(email)
                daily_count = cache.get(cache_key, 0)
                if daily_count < RESEND_DAILY_LIMIT:
                    sent = send_email_confirmation(request, user, signup=False, email=email)
                    if sent:
                        cache.set(cache_key, daily_count + 1, RESEND_DAILY_LIMIT_SECONDS)
        messages.info(
            request,
            'Se o e-mail informado tiver um cadastro pendente, um novo link de confirmação foi '
            'enviado. Confira também a caixa de spam. Se você já solicitou um reenvio há pouco '
            'tempo, ou atingiu o limite diário de reenvios, tente novamente mais tarde.'
        )
        return redirect('account_email_verification_sent')


class ProfileCompletionView(LoginRequiredMixin, FormView):
    """Story 3.5: nome/sobrenome obrigatorios no primeiro login -- RequireCompleteAccountMiddleware
    redireciona pra ca antes de qualquer outra tela."""
    template_name = 'accounts/complete_profile.html'
    form_class = ProfileCompletionForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Cadastro concluído com sucesso!')
        return super().form_valid(form)

    def get_success_url(self):
        """Valida 'next' contra open redirect (Story 3.5 nunca pediu redirecionar pra fora do
        site) -- sem isso, um link tipo ?next=https://phishing.example seria seguido as cegas
        logo apos o usuario confirmar a propria senha, um vetor de phishing crivel."""
        next_url = self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url, allowed_hosts={self.request.get_host()}, require_https=self.request.is_secure(),
        ):
            return next_url
        return str(reverse_lazy('home'))


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
        user.preferred_theme = 'dark' if user.preferred_theme == 'light' else 'light'
        user.save(update_fields=['preferred_theme'])
    else:
        # Para usuarios anonimos, usar sessao
        current = request.session.get('theme', 'light')
        request.session['theme'] = 'dark' if current == 'light' else 'light'

    referer = request.META.get('HTTP_REFERER', '/')
    return redirect(referer)
