from django.urls import path
from .views import (
    ConfirmEmailView, CustomSignupView, ProfileCompletionView, ProfileUpdateView,
    ResendConfirmationEmailView, toggle_theme,
)

urlpatterns = [
    path('signup/', CustomSignupView.as_view(), name='account_signup'),
    # 'resend/' PRECISA vir antes do path com <str:key> abaixo -- key aceita qualquer string sem
    # barra, entao "resend" tambem bateria como chave de confirmacao se a ordem fosse invertida.
    path('confirm-email/resend/', ResendConfirmationEmailView.as_view(), name='resend_confirmation'),
    # Mesmo path/nome de rota do allauth (accounts/confirm-email/<key>/, account_confirm_email) --
    # precisa vir ANTES do include('allauth.urls') no urls.py raiz pra essa view ganhar
    # precedencia (mesmo mecanismo ja usado por account_signup acima).
    path('confirm-email/<str:key>/', ConfirmEmailView.as_view(), name='account_confirm_email'),
    path('complete-profile/', ProfileCompletionView.as_view(), name='complete_profile'),
    path('profile/', ProfileUpdateView.as_view(), name='profile'),
    path('theme/toggle/', toggle_theme, name='toggle_theme'),
]
