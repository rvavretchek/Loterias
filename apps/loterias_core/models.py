from django.core.exceptions import ValidationError
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


class HitNotification(models.Model):
    """Marca um GeneratedBet que teve pelo menos 1 acerto contra o resultado oficial."""
    bet = models.OneToOneField(
        GeneratedBet,
        on_delete=models.CASCADE,
        related_name='notification',
        verbose_name='Jogo'
    )
    won = models.BooleanField(default=False, verbose_name='Premiado')
    is_read = models.BooleanField(default=False, verbose_name='Lida')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    class Meta:
        verbose_name = 'Notificacao de Acerto'
        verbose_name_plural = 'Notificacoes de Acerto'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['is_read'])]

    def __str__(self):
        return f'Notificacao - {self.bet}'


class NotificationPreference(models.Model):
    """Preferencia de canal de aviso de acerto por usuario (site e/ou e-mail)."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preference',
        verbose_name='Usuario'
    )
    site_enabled = models.BooleanField(default=True, verbose_name='Aviso no site')
    email_enabled = models.BooleanField(default=False, verbose_name='Aviso por e-mail')

    class Meta:
        verbose_name = 'Preferencia de Notificacao'
        verbose_name_plural = 'Preferencias de Notificacao'
        constraints = [
            models.CheckConstraint(
                check=models.Q(site_enabled=True) | models.Q(email_enabled=True),
                name='notificationpreference_at_least_one_channel_enabled',
            ),
        ]

    def __str__(self):
        return f'Preferencia de notificacao - {self.user.email}'

    def clean(self):
        super().clean()
        if not self.site_enabled and not self.email_enabled:
            raise ValidationError(
                'Pelo menos um canal de aviso (site ou e-mail) precisa continuar ativo.'
            )


class PrizeTier(models.Model):
    """Faixa de premiacao vigente por Jogo/quantidade de acertos, capturada mensalmente
    (Story 2.8/AD-10). So os 3 reference_month mais recentes por (game, hits) sao retidos."""
    game = models.CharField(max_length=20, choices=GeneratedBet.GAME_CHOICES, verbose_name='Jogo')
    hits = models.PositiveIntegerField(verbose_name='Acertos')
    value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Valor')
    winners = models.PositiveIntegerField(default=0, verbose_name='Ganhadores')
    reference_month = models.DateField(verbose_name='Mes de Referencia')

    class Meta:
        verbose_name = 'Faixa de Premiacao'
        verbose_name_plural = 'Faixas de Premiacao'
        unique_together = ('game', 'hits', 'reference_month')
        ordering = ['-reference_month']

    def __str__(self):
        return f'{self.game} - {self.hits} acertos ({self.reference_month:%m/%Y})'


CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS = 8


class CaptureFailureAlert(models.Model):
    """Registra que o operador ja foi avisado da falha de captura de um par Jogo/Concurso
    (Story 2.9) -- garante exatamente 1 e-mail de alerta por par, mesmo que a falha persista por
    varias execucoes --final."""
    game = models.CharField(max_length=20, choices=GeneratedBet.GAME_CHOICES, verbose_name='Jogo')
    contest = models.CharField(max_length=20, verbose_name='Concurso')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    class Meta:
        verbose_name = 'Alerta de Falha de Captura'
        verbose_name_plural = 'Alertas de Falha de Captura'
        unique_together = ('game', 'contest')

    def __str__(self):
        return f'Alerta - {self.game}/{self.contest}'
