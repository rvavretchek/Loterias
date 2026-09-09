from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('gerar/', views.create_bet_view, name='create_bet'),
    path('jogo/manual/', views.save_manual_bet_view, name='save_manual_bet'),
    path('jogo/<int:pk>/', views.bet_detail_view, name='bet_detail'),
    path('jogo/<int:pk>/refazer/', views.regenerate_bet_view, name='regenerate_bet'),
    path('jogo/<int:pk>/excluir/', views.delete_bet_view, name='delete_bet'),
    path('jogo/<int:pk>/verificar/', views.check_bet_result_view, name='check_bet_result'),
    path('historico/', views.history_view, name='history'),
    path('estatisticas/', views.statistics_view, name='statistics'),
    path('notificacoes/', views.notifications_view, name='notifications'),
    path('api/gerar/', views.api_create_bet_view, name='api_create_bet'),
]
