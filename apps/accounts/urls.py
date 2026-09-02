from django.urls import path
from .views import CustomSignupView, ProfileUpdateView, toggle_theme

urlpatterns = [
    path('signup/', CustomSignupView.as_view(), name='account_signup'),
    path('profile/', ProfileUpdateView.as_view(), name='profile'),
    path('theme/toggle/', toggle_theme, name='toggle_theme'),
]
