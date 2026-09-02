from django.db import models
from django.conf import settings


# Configuracoes dos jogos
MEGA_SENA = {'nome': 'Mega-sena', 'apostas': 6, 'numeros': 60, 'trevos': 0, 'qtd_trevos': 0}
MILIONARIA = {'nome': 'Milionaria', 'apostas': 6, 'numeros': 50, 'trevos': 2, 'qtd_trevos': 6}
LOTOMANIA = {'nome': 'Lotomania', 'apostas': 50, 'numeros': 100, 'trevos': 0, 'qtd_trevos': 0}
LOTOFACIL = {'nome': 'Lotofacil', 'apostas': 15, 'numeros': 25, 'trevos': 0, 'qtd_trevos': 0}
QUINA = {'nome': 'Quina', 'apostas': 5, 'numeros': 80, 'trevos': 0, 'qtd_trevos': 0}
DUPLASENA = {'nome': 'Dupla-Sena', 'apostas': 6, 'numeros': 50, 'trevos': 0, 'qtd_trevos': 0}

JOGOS_CONFIG = {
    'Mega-sena': MEGA_SENA,
    'Milionaria': MILIONARIA,
    'Lotomania': LOTOMANIA,
    'Lotofacil': LOTOFACIL,
    'Quina': QUINA,
    'Dupla-Sena': DUPLASENA
}

JOGOS_COM_REGRA_SEQUENCIA = {'Mega-sena', 'Milionaria', 'Quina', 'Dupla-Sena'}
INTERVALO_MIN_SEQUENCIA = 5


class JogoGerado(models.Model):
    """Modelo para armazenar jogos gerados por usuario."""
    JOGOS_CHOICES = [
        ('Mega-sena', 'Mega-sena'),
        ('Milionaria', 'Milionaria'),
        ('Lotomania', 'Lotomania'),
        ('Lotofacil', 'Lotofacil'),
        ('Quina', 'Quina'),
        ('Dupla-Sena', 'Dupla-Sena'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='jogos',
        verbose_name='Usuario'
    )
    jogo = models.CharField(max_length=20, choices=JOGOS_CHOICES, verbose_name='Jogo')
    concurso = models.CharField(max_length=20, verbose_name='Concurso')
    numeros = models.JSONField(verbose_name='Numeros')
    trevos = models.JSONField(default=list, blank=True, verbose_name='Trevos')
    pares_sequenciais = models.PositiveIntegerField(default=0, verbose_name='Pares Sequenciais')
    manual = models.BooleanField(default=False, verbose_name='Jogo Manual')
    resultado_verificado = models.BooleanField(default=False, verbose_name='Resultado verificado')
    acertos = models.PositiveIntegerField(default=0, verbose_name='Acertos')
    premio = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Premio')
    premio_descricao = models.CharField(max_length=120, blank=True, default='', verbose_name='Descricao do premio')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        verbose_name = 'Jogo Gerado'
        verbose_name_plural = 'Jogos Gerados'
        ordering = ['-criado_em']
        indexes = [
            models.Index(fields=['usuario', 'jogo']),
            models.Index(fields=['criado_em']),
        ]

    def __str__(self):
        nums = ' - '.join(f'{n:02d}' for n in self.numeros)
        return f'{self.jogo} - Concurso {self.concurso}: {nums}'

    def get_numeros_formatados(self):
        """Retorna numeros formatados para exibicao."""
        return '   '.join(f'{n:02d}' for n in self.numeros)

    def get_trevos_formatados(self):
        """Retorna trevos formatados para exibicao."""
        if self.trevos:
            return '   '.join(f'{t:02d}' for t in self.trevos)
        return None

    def tem_sequencia(self):
        """Verifica se o jogo tem pares sequenciais."""
        return self.pares_sequenciais > 0


class ResultadoLoteria(models.Model):
    """Resultado oficial capturado da CEF para validacao do jogo do usuario."""
    JOGOS_CHOICES = JogoGerado.JOGOS_CHOICES

    jogo = models.CharField(max_length=20, choices=JOGOS_CHOICES, verbose_name='Jogo')
    concurso = models.CharField(max_length=20, verbose_name='Concurso')
    numeros = models.JSONField(verbose_name='Numeros sorteados')
    trevos = models.JSONField(default=list, blank=True, verbose_name='Trevos sorteados')
    premiacoes = models.JSONField(default=dict, blank=True, verbose_name='Premiacoes')
    origem = models.CharField(max_length=50, default='CEF', verbose_name='Origem')
    capturado_em = models.DateTimeField(auto_now_add=True, verbose_name='Capturado em')

    class Meta:
        verbose_name = 'Resultado Oficial'
        verbose_name_plural = 'Resultados Oficiais'
        unique_together = ['jogo', 'concurso']
        ordering = ['-capturado_em']

    def __str__(self):
        return f'{self.jogo} - Concurso {self.concurso}'


class EstatisticaJogo(models.Model):
    """Estatisticas agregadas por tipo de jogo e usuario."""
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='estatisticas',
        verbose_name='Usuario'
    )
    jogo = models.CharField(max_length=20, choices=JogoGerado.JOGOS_CHOICES, verbose_name='Jogo')
    total_jogos = models.PositiveIntegerField(default=0, verbose_name='Total de Jogos')
    total_com_sequencia = models.PositiveIntegerField(default=0, verbose_name='Jogos com Sequencia')
    total_sem_sequencia = models.PositiveIntegerField(default=0, verbose_name='Jogos sem Sequencia')
    numero_mais_frequente = models.JSONField(default=list, verbose_name='Numeros Mais Frequentes')
    ultima_atualizacao = models.DateTimeField(auto_now=True, verbose_name='Ultima Atualizacao')

    class Meta:
        verbose_name = 'Estatistica'
        verbose_name_plural = 'Estatisticas'
        unique_together = ['usuario', 'jogo']

    def __str__(self):
        return f'Estatisticas - {self.jogo} ({self.usuario.email})'
