from django.urls import path
from . import views

app_name = 'jogos'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('novo/', views.novo_jogo, name='novo_jogo'),
    path('gerar/', views.gerar_jogo_api, name='gerar_jogo'),
    path('historico/', views.historico, name='historico'),
    path('jogo/<int:jogo_id>/', views.detalhes_jogo, name='detalhes_jogo'),
    path('jogo/<int:jogo_id>/refazer/', views.refazer_jogo, name='refazer_jogo'),
    path('jogo/<int:jogo_id>/conferir/', views.conferir_jogo, name='conferir_jogo'),
    path('resultados/', views.resultados, name='resultados'),
    path('resultados/buscar/', views.buscar_resultado_api, name='buscar_resultado'),
    path('resultados/cadastrar/', views.cadastrar_resultado, name='cadastrar_resultado'),
]
