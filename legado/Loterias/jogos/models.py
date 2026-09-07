from django.conf import settings
from django.db import models


class TipoJogo(models.Model):
    """Configuração de cada modalidade de loteria."""

    nome = models.CharField('Nome', max_length=50, unique=True)
    slug_api = models.CharField(
        'Slug API Caixa', max_length=30,
        help_text='Identificador usado na URL da API. Ex: megasena, lotofacil',
    )
    cor = models.CharField('Cor (hex)', max_length=7, default='#209869')
    qtd_dezenas = models.PositiveIntegerField('Qtd de dezenas por aposta')
    max_numero = models.PositiveIntegerField('Número máximo')
    qtd_trevos = models.PositiveIntegerField('Qtd de trevos', default=0)
    max_trevo = models.PositiveIntegerField('Trevo máximo', default=0)
    aplica_regra_sequencia = models.BooleanField(
        'Aplica regra de sequência',
        default=False,
        help_text='Máx 1 par consecutivo por jogo, intervalo mín. 5 jogos.',
    )
    tem_segundo_sorteio = models.BooleanField('Tem 2o sorteio', default=False)

    class Meta:
        verbose_name = 'Tipo de Jogo'
        verbose_name_plural = 'Tipos de Jogo'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Concurso(models.Model):
    """Resultado oficial de um concurso da Caixa."""

    tipo_jogo = models.ForeignKey(
        TipoJogo, on_delete=models.CASCADE, related_name='concursos',
    )
    numero = models.PositiveIntegerField('Número do concurso')
    data_sorteio = models.DateField('Data do sorteio', null=True, blank=True)
    dezenas = models.JSONField('Dezenas sorteadas', default=list)
    dezenas_segundo_sorteio = models.JSONField(
        'Dezenas 2o sorteio', default=list, blank=True,
    )
    trevos_sorteados = models.JSONField(
        'Trevos sorteados', default=list, blank=True,
    )
    valor_estimado_proximo = models.DecimalField(
        'Valor estimado próximo', max_digits=15, decimal_places=2,
        null=True, blank=True,
    )
    proximo_concurso = models.PositiveIntegerField(
        'Próximo concurso', null=True, blank=True,
    )
    dados_completos = models.JSONField(
        'Resposta completa da API', null=True, blank=True,
    )
    cadastrado_manualmente = models.BooleanField(
        'Cadastrado manualmente', default=False,
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Concurso'
        verbose_name_plural = 'Concursos'
        unique_together = ('tipo_jogo', 'numero')
        ordering = ['-numero']

    def __str__(self):
        return f"{self.tipo_jogo.nome} — Concurso {self.numero}"


class JogoGerado(models.Model):
    """Jogo gerado por um usuário."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='jogos',
    )
    tipo_jogo = models.ForeignKey(
        TipoJogo, on_delete=models.CASCADE, related_name='jogos_gerados',
    )
    concurso = models.ForeignKey(
        Concurso, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='jogos_apostados',
    )
    numero_concurso = models.PositiveIntegerField('Número do concurso')
    numeros = models.JSONField('Números apostados', default=list)
    trevos = models.JSONField('Trevos apostados', default=list, blank=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    # Resultado da conferência
    acertos = models.PositiveIntegerField('Acertos', null=True, blank=True)
    acertos_segundo_sorteio = models.PositiveIntegerField(
        'Acertos 2o sorteio', null=True, blank=True,
    )
    acertos_trevos = models.PositiveIntegerField(
        'Acertos trevos', null=True, blank=True,
    )
    conferido = models.BooleanField('Conferido', default=False)
    faixa_premio = models.CharField(
        'Faixa de premiação', max_length=100, blank=True, default='',
    )

    class Meta:
        verbose_name = 'Jogo Gerado'
        verbose_name_plural = 'Jogos Gerados'
        ordering = ['-criado_em']

    def __str__(self):
        nums = ', '.join(f'{n:02d}' for n in self.numeros[:6])
        return f"{self.tipo_jogo.nome} #{self.numero_concurso} — {nums}..."
