from django.contrib.auth import authenticate, login, logout
from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings

from .forms import RegistroForm, LoginEmailForm
from .tokens import account_activation_token
from .models import CustomUser


def registro_view(request):
    """Auto-cadastro com envio de e-mail de verificação."""
    if request.user.is_authenticated:
        return redirect('jogos:dashboard')

    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            _enviar_email_ativacao(request, user)
            return render(request, 'accounts/ativacao_enviada.html', {'email': user.email})
    else:
        form = RegistroForm()

    return render(request, 'accounts/registro.html', {'form': form})


def _enviar_email_ativacao(request, user):
    """Envia e-mail com link de ativação."""
    current_site = get_current_site(request)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = account_activation_token.make_token(user)

    link = f"http://{current_site.domain}/conta/ativar/{uid}/{token}/"

    subject = 'Ative sua conta — Gerador de Loterias'
    message = render_to_string('accounts/ativacao_email.html', {
        'user': user,
        'link': link,
        'domain': current_site.domain,
    })

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def ativar_conta_view(request, uidb64, token):
    """Ativa a conta do usuário via link recebido por e-mail."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.email_confirmed = True
        user.save()
        login(request, user)
        messages.success(request, f'Bem-vindo(a), {user.first_name}! Sua conta foi ativada com sucesso.')
        return redirect('jogos:dashboard')
    else:
        return render(request, 'accounts/ativacao_invalida.html')


def login_view(request):
    """Login por e-mail + senha."""
    if request.user.is_authenticated:
        return redirect('jogos:dashboard')

    if request.method == 'POST':
        form = LoginEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].lower().strip()
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            if user is not None:
                if not user.email_confirmed:
                    messages.warning(request, 'Confirme seu e-mail antes de fazer login. Verifique sua caixa de entrada.')
                    return render(request, 'accounts/login.html', {'form': form})
                login(request, user)
                next_url = request.GET.get('next', 'jogos:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'E-mail ou senha inválidos.')
    else:
        form = LoginEmailForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Logout."""
    logout(request)
    messages.info(request, 'Você saiu da sua conta.')
    return redirect('accounts:login')


def perfil_view(request):
    """Página de perfil — atualizar tema."""
    if request.method == 'POST':
        tema = request.POST.get('tema_preferido', 'light')
        if tema in ('light', 'dark'):
            request.user.tema_preferido = tema
            request.user.save(update_fields=['tema_preferido'])
            messages.success(request, 'Preferências atualizadas.')
        return redirect('accounts:perfil')
    return render(request, 'accounts/perfil.html')
