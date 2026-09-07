from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('gerar/', views.gerar_jogo, name='gerar_jogo'),
    path('jogo/manual/', views.salvar_jogo_manual, name='salvar_jogo_manual'),
    path('jogo/<int:pk>/', views.detalhes_jogo, name='detalhes_jogo'),
    path('jogo/<int:pk>/refazer/', views.refazer_jogo, name='refazer_jogo'),
    path('jogo/<int:pk>/excluir/', views.excluir_jogo, name='excluir_jogo'),
    path('jogo/<int:pk>/verificar/', views.verificar_resultado_jogo, name='verificar_resultado_jogo'),
    path('historico/', views.historico, name='historico'),
    path('estatisticas/', views.estatisticas, name='estatisticas'),
    path('api/gerar/', views.api_gerar_jogo, name='api_gerar_jogo'),
]
