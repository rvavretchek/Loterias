from django.urls import path
from .views import (
    CustomSignupView, ProfileCompletionView, ProfileUpdateView,
    ResendConfirmationEmailView, toggle_theme,
)

urlpatterns = [
    path('signup/', CustomSignupView.as_view(), name='account_signup'),
    path('confirm-email/resend/', ResendConfirmationEmailView.as_view(), name='resend_confirmation'),
    path('complete-profile/', ProfileCompletionView.as_view(), name='complete_profile'),
    path('profile/', ProfileUpdateView.as_view(), name='profile'),
    path('theme/toggle/', toggle_theme, name='toggle_theme'),
]
