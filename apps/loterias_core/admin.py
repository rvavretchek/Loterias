from django.contrib import admin
from .models import JogoGerado, EstatisticaJogo


@admin.register(JogoGerado)
class JogoGeradoAdmin(admin.ModelAdmin):
    list_display = ('jogo', 'concurso', 'usuario', 'pares_sequenciais', 'criado_em')
    list_filter = ('jogo', 'criado_em', 'pares_sequenciais')
    search_fields = ('concurso', 'usuario__email', 'usuario__first_name')
    date_hierarchy = 'criado_em'
    readonly_fields = ('pares_sequenciais', 'criado_em', 'atualizado_em')


@admin.register(EstatisticaJogo)
class EstatisticaJogoAdmin(admin.ModelAdmin):
    list_display = ('jogo', 'usuario', 'total_jogos', 'ultima_atualizacao')
    list_filter = ('jogo', 'ultima_atualizacao')
    search_fields = ('usuario__email',)
