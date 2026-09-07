from django.contrib import admin
from .models import TipoJogo, Concurso, JogoGerado


@admin.register(TipoJogo)
class TipoJogoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug_api', 'qtd_dezenas', 'max_numero',
                    'aplica_regra_sequencia', 'tem_segundo_sorteio')
    list_filter = ('aplica_regra_sequencia', 'tem_segundo_sorteio')


@admin.register(Concurso)
class ConcursoAdmin(admin.ModelAdmin):
    list_display = ('tipo_jogo', 'numero', 'data_sorteio', 'cadastrado_manualmente',
                    'atualizado_em')
    list_filter = ('tipo_jogo', 'cadastrado_manualmente')
    search_fields = ('numero',)
    ordering = ('-numero',)


@admin.register(JogoGerado)
class JogoGeradoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo_jogo', 'numero_concurso', 'conferido',
                    'acertos', 'criado_em')
    list_filter = ('tipo_jogo', 'conferido', 'usuario')
    search_fields = ('numero_concurso', 'usuario__email')
    ordering = ('-criado_em',)
