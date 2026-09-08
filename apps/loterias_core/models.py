from django.db import models
from django.conf import settings


# Configuracoes dos jogos
MEGA_SENA = {'name': 'Mega-sena', 'bets_count': 6, 'numbers_count': 60, 'clovers': 0, 'clovers_count': 0}
MILIONARIA = {'name': 'Milionaria', 'bets_count': 6, 'numbers_count': 50, 'clovers': 2, 'clovers_count': 6}
LOTOMANIA = {'name': 'Lotomania', 'bets_count': 50, 'numbers_count': 100, 'clovers': 0, 'clovers_count': 0}
LOTOFACIL = {'name': 'Lotofacil', 'bets_count': 15, 'numbers_count': 25, 'clovers': 0, 'clovers_count': 0}
QUINA = {'name': 'Quina', 'bets_count': 5, 'numbers_count': 80, 'clovers': 0, 'clovers_count': 0}
DUPLASENA = {'name': 'Dupla-Sena', 'bets_count': 6, 'numbers_count': 50, 'clovers': 0, 'clovers_count': 0}

GAMES_CONFIG = {
    'Mega-sena': MEGA_SENA,
    'Milionaria': MILIONARIA,
    'Lotomania': LOTOMANIA,
    'Lotofacil': LOTOFACIL,
    'Quina': QUINA,
    'Dupla-Sena': DUPLASENA
}

GAMES_WITH_SEQUENCE_RULE = {'Mega-sena', 'Milionaria', 'Quina', 'Dupla-Sena'}
MIN_SEQUENCE_INTERVAL = 5


class GeneratedBet(models.Model):
    """Modelo para armazenar jogos gerados por usuario."""
    GAME_CHOICES = [
        ('Mega-sena', 'Mega-sena'),
        ('Milionaria', 'Milionaria'),
        ('Lotomania', 'Lotomania'),
        ('Lotofacil', 'Lotofacil'),
        ('Quina', 'Quina'),
        ('Dupla-Sena', 'Dupla-Sena'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bets',
        verbose_name='Usuario'
    )
    game = models.CharField(max_length=20, choices=GAME_CHOICES, verbose_name='Jogo')
    contest = models.CharField(max_length=20, verbose_name='Concurso')
    numbers = models.JSONField(verbose_name='Numeros')
    clovers = models.JSONField(default=list, blank=True, verbose_name='Trevos')
    sequential_pairs = models.PositiveIntegerField(default=0, verbose_name='Pares Sequenciais')
    manual = models.BooleanField(default=False, verbose_name='Jogo Manual')
    result_checked = models.BooleanField(default=False, verbose_name='Resultado verificado')
    hits = models.PositiveIntegerField(default=0, verbose_name='Acertos')
    prize = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Premio')
    prize_description = models.CharField(max_length=120, blank=True, default='', verbose_name='Descricao do premio')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        verbose_name = 'Jogo Gerado'
        verbose_name_plural = 'Jogos Gerados'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'game']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        nums = ' - '.join(f'{n:02d}' for n in self.numbers)
        return f'{self.game} - Concurso {self.contest}: {nums}'

    def get_formatted_numbers(self):
        """Retorna numeros formatados para exibicao."""
        return '   '.join(f'{n:02d}' for n in self.numbers)

    def get_formatted_clovers(self):
        """Retorna trevos formatados para exibicao."""
        if self.clovers:
            return '   '.join(f'{t:02d}' for t in self.clovers)
        return None

    def has_sequence(self):
        """Verifica se o jogo tem pares sequenciais."""
        return self.sequential_pairs > 0


class LotteryResult(models.Model):
    """Resultado oficial capturado da CEF para validacao do jogo do usuario."""
    GAME_CHOICES = GeneratedBet.GAME_CHOICES

    game = models.CharField(max_length=20, choices=GAME_CHOICES, verbose_name='Jogo')
    contest = models.CharField(max_length=20, verbose_name='Concurso')
    numbers = models.JSONField(verbose_name='Numeros sorteados')
    clovers = models.JSONField(default=list, blank=True, verbose_name='Trevos sorteados')
    prizes = models.JSONField(default=dict, blank=True, verbose_name='Premiacoes')
    source = models.CharField(max_length=50, default='CEF', verbose_name='Origem')
    captured_at = models.DateTimeField(auto_now_add=True, verbose_name='Capturado em')

    class Meta:
        verbose_name = 'Resultado Oficial'
        verbose_name_plural = 'Resultados Oficiais'
        unique_together = ['game', 'contest']
        ordering = ['-captured_at']

    def __str__(self):
        return f'{self.game} - Concurso {self.contest}'


class GameStatistics(models.Model):
    """Estatisticas agregadas por tipo de jogo e usuario."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='statistics',
        verbose_name='Usuario'
    )
    game = models.CharField(max_length=20, choices=GeneratedBet.GAME_CHOICES, verbose_name='Jogo')
    total_bets = models.PositiveIntegerField(default=0, verbose_name='Total de Jogos')
    total_with_sequence = models.PositiveIntegerField(default=0, verbose_name='Jogos com Sequencia')
    total_without_sequence = models.PositiveIntegerField(default=0, verbose_name='Jogos sem Sequencia')
    most_frequent_numbers = models.JSONField(default=list, verbose_name='Numeros Mais Frequentes')
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Ultima Atualizacao')

    class Meta:
        verbose_name = 'Estatistica'
        verbose_name_plural = 'Estatisticas'
        unique_together = ['user', 'game']

    def __str__(self):
        return f'Estatisticas - {self.game} ({self.user.email})'
