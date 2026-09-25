from django.core.exceptions import ValidationError
from django.db import models, transaction, IntegrityError
from django.conf import settings


def normalize_contest(raw):
    """Normaliza um numero de concurso digitado pelo usuario pra uma forma canonica (Story 2.12):
    remove zeros a esquerda convertendo pra inteiro e re-serializando, garantindo que duas grafias
    do mesmo concurso real (ex. '2500' e '02500') nunca sejam tratadas como concursos distintos em
    nenhum ponto que compara/grava `contest` (bloqueio de concurso ja sorteado, duplicata,
    LotteryResult, purga manual). Levanta ValueError pra qualquer valor vazio ou nao numerico --
    nunca grava/compara um concurso invalido silenciosamente."""
    stripped = raw.strip()
    if not stripped.isdecimal():
        raise ValueError(f'Numero de concurso invalido: {raw!r}')
    return str(int(stripped))


class NormalizesContestOnSave(models.Model):
    """Mixin abstrato (retro do Epic 2, item 7): normaliza `contest` (melhor esforco) em QUALQUER
    caminho de escrita -- admin, views, shell, futuros entry points -- sem depender de cada um
    lembrar de chamar normalize_contest() antes de salvar. Antes desta mixin, a Story 2.16 precisou
    duplicar essa mesma normalizacao manualmente no form do admin (`_NormalizedContestFormMixin`)
    porque o model nao garantia isso sozinho; o form do admin continua existindo pra dar um erro de
    validacao amigavel a quem digita algo invalido. Este save() nunca rejeita: um `contest` legado
    nao-numerico (ex. edicao especial antiga) e mantido como esta -- rejeitar entrada e trabalho da
    camada de formulario/view (que ve o usuario digitando), nao do model (que precisa continuar
    aceitando dado historico ja gravado antes da Story 2.12)."""
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        try:
            self.contest = normalize_contest(self.contest)
        except (ValueError, AttributeError):
            pass
        super().save(*args, **kwargs)


# Configuracoes dos jogos. 'clovers': quantos trevos o jogo exige escolher (0 se o jogo nao usa
# trevo). 'clovers_count': tamanho do pool de trevos disponiveis pra escolher (0 se nao aplicavel).
# Na +Milionaria, por exemplo, o jogador escolhe 2 trevos ('clovers') dentre 6 possiveis
# ('clovers_count').
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

# Regras de Geracao personalizaveis (Story 4.3, AD-11). RULE_NAMES_BY_GAME e a fonte unica de
# quais rule_name existem por Jogo -- nenhum outro lugar hardcoda esses nomes. 'kind' diz se a
# regra usa numeric_value ('int') ou choice_value ('choice').
DISTRIBUTION_CHOICES = [
    ('homogenea', 'Homogênea'),
    ('totalmente_aleatoria', 'Totalmente Aleatória'),
]
RULE_DEFINITIONS = {
    'limit_sequence_count': {
        'label': 'Limita quantidade de números em sequência', 'kind': 'int',
        'explanation': 'Sequência é quando 2 ou mais números sorteados são seguidos (ex.: 23 e 24). '
            'Esta regra limita o tamanho da maior sequência do jogo — valor 2 permite um par como '
            '23-24, mas nunca um trio como 23-24-25.',
    },
    'limit_sequence_pairs': {
        'label': 'Limita quantidade de sequências num jogo', 'kind': 'int',
        'explanation': 'Controla quantos blocos de números seguidos podem existir no mesmo jogo — '
            'não o tamanho de cada bloco, e sim quantos blocos ao todo.',
    },
    'limit_row_count': {
        'label': 'Limita quantidade de números na mesma linha do volante', 'kind': 'int',
        'explanation': 'Limita quantos números sorteados podem cair na mesma linha do volante oficial.',
    },
    'limit_column_count': {
        'label': 'Limita quantidade de números na mesma coluna do volante', 'kind': 'int',
        'explanation': 'Limita quantos números sorteados podem cair na mesma coluna do volante oficial.',
    },
    'distribution_type': {
        'label': 'Tipo de distribuição', 'kind': 'choice',
        'explanation': 'Homogênea espalha os números por igual entre as faixas do volante, em vez '
            'de deixar concentrar tudo numa região. Totalmente Aleatória sorteia sem nenhuma '
            'preferência de distribuição.',
    },
    'limit_min_gap_between_sequences': {
        'label': 'Distância mínima entre sequências', 'kind': 'int',
        'explanation': 'Quando o jogo tem mais de uma sequência, exige pelo menos essa quantidade de '
            'números não sorteados entre uma sequência e a próxima.',
    },
    'limit_min_sequences': {
        'label': 'Quantidade mínima de sequências', 'kind': 'int',
        'explanation': 'Exige que o jogo tenha pelo menos essa quantidade de sequências (blocos de '
            'números seguidos) — o oposto de limitar um máximo.',
    },
}
RULE_NAMES_BY_GAME = {
    'Mega-sena': [
        'limit_sequence_count', 'limit_sequence_pairs', 'limit_row_count',
        'limit_column_count', 'distribution_type',
    ],
    'Milionaria': [
        'limit_sequence_count', 'limit_sequence_pairs', 'limit_row_count',
        'limit_column_count', 'distribution_type',
    ],
    'Quina': [
        'limit_sequence_count', 'limit_sequence_pairs', 'limit_row_count',
        'limit_column_count', 'distribution_type',
    ],
    'Dupla-Sena': [
        'limit_sequence_count', 'limit_sequence_pairs', 'limit_row_count',
        'limit_column_count', 'distribution_type',
    ],
    'Lotofacil': [
        'limit_sequence_count', 'limit_sequence_pairs', 'limit_row_count',
        'limit_column_count', 'distribution_type', 'limit_min_gap_between_sequences',
        'limit_min_sequences',
    ],
    'Lotomania': ['limit_sequence_count', 'limit_min_gap_between_sequences', 'limit_min_sequences'],
}
# Grid do volante oficial (linhas, colunas) -- base das regras de linha/coluna (PRD 8.5). Mega-Sena
# (6x10) e Lotofacil (5x5) confirmados com fonte; +Milionaria (5x10), Quina (8x10) e Dupla-Sena
# (5x10) confirmados pelo Boss em 2026-09-19.
GAME_GRID = {
    'Mega-sena': (6, 10),
    'Milionaria': (5, 10),
    'Quina': (8, 10),
    'Dupla-Sena': (5, 10),
    'Lotofacil': (5, 5),
}
# Regras que controlam sequencia (usadas pelo aviso "sem protecao de sequencia" da tela de edicao).
SEQUENCE_RULE_NAMES = ('limit_sequence_count', 'limit_sequence_pairs')
RULE_NAME_CHOICES = [
    (name, RULE_DEFINITIONS[name]['label'])
    for name in RULE_DEFINITIONS
    if any(name in names for names in RULE_NAMES_BY_GAME.values())
]


class GeneratedBet(NormalizesContestOnSave):
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


class LotteryResultManager(models.Manager):
    def save_official_result(self, game, contest, result):
        """Grava/atualiza o resultado oficial de um Jogo+Concurso (retro do Epic 2, itens 1 e 7):
        fonte unica do mapeamento resultado->defaults e da protecao de corrida via
        `unique_together (game, contest)`, usada pelo cron diario e pelas duas telas de conferencia
        manual -- antes, as 3 chamadas duplicavam a mesma logica sem nenhuma das 3 tratar a corrida
        entre elas (cron + verificacao manual do mesmo par podem rodar ao mesmo tempo). Segue a
        receita da propria documentacao do Django pra `update_or_create` sob corrida: tenta de novo
        dentro de um `atomic()` novo se a 1a tentativa esbarrar no `unique_together`."""
        defaults = {
            'numbers': result.get('numbers', []),
            'clovers': result.get('clovers', []),
            'prizes': result.get('prizes', {}),
            'numbers_second_draw': result.get('numbers_second_draw', []),
            'prizes_second_draw': result.get('prizes_second_draw', {}),
            'source': 'CEF',
        }
        try:
            with transaction.atomic():
                return self.update_or_create(game=game, contest=contest, defaults=defaults)
        except IntegrityError:
            with transaction.atomic():
                return self.update_or_create(game=game, contest=contest, defaults=defaults)


class LotteryResult(NormalizesContestOnSave):
    """Resultado oficial capturado da CEF para validacao do jogo do usuario."""
    GAME_CHOICES = GeneratedBet.GAME_CHOICES

    objects = LotteryResultManager()

    game = models.CharField(max_length=20, choices=GAME_CHOICES, verbose_name='Jogo')
    contest = models.CharField(max_length=20, verbose_name='Concurso')
    numbers = models.JSONField(verbose_name='Numeros sorteados')
    clovers = models.JSONField(default=list, blank=True, verbose_name='Trevos sorteados')
    prizes = models.JSONField(default=dict, blank=True, verbose_name='Premiacoes')
    numbers_second_draw = models.JSONField(
        default=list, blank=True, verbose_name='Numeros sorteados (2o sorteio)',
    )
    prizes_second_draw = models.JSONField(
        default=dict, blank=True, verbose_name='Premiacoes (2o sorteio)',
    )
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


class CaptureFailureAlert(NormalizesContestOnSave):
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


class GenerationRule(models.Model):
    """Regra de geracao personalizada por usuario+Jogo (Story 4.3, AD-11/AD-13). Ausencia de
    linhas pra um (user, game) e o estado 'default do sistema'; desligar uma regra nunca deleta
    a linha (so 'Restaurar padrao' deleta)."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='generation_rules',
        verbose_name='Usuario'
    )
    game = models.CharField(max_length=20, choices=GeneratedBet.GAME_CHOICES, verbose_name='Jogo')
    rule_name = models.CharField(max_length=40, choices=RULE_NAME_CHOICES, verbose_name='Regra')
    enabled = models.BooleanField(default=False, verbose_name='Ligada')
    numeric_value = models.IntegerField(null=True, blank=True, verbose_name='Valor numerico')
    choice_value = models.CharField(max_length=30, null=True, blank=True, verbose_name='Valor de escolha')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        verbose_name = 'Regra de Geracao'
        verbose_name_plural = 'Regras de Geracao'
        unique_together = ('user', 'game', 'rule_name')
        constraints = [
            models.CheckConstraint(
                check=~models.Q(numeric_value__isnull=False, choice_value__isnull=False),
                name='generationrule_not_both_numeric_and_choice_value',
            ),
        ]

    def __str__(self):
        return f'{self.game} - {self.rule_name} ({"ligada" if self.enabled else "desligada"})'

    def clean(self):
        super().clean()
        if self.rule_name not in RULE_NAMES_BY_GAME.get(self.game, []):
            raise ValidationError(f'A regra {self.rule_name} nao existe para o jogo {self.game}.')
        if self.numeric_value is not None and self.choice_value is not None:
            raise ValidationError('Uma regra nao pode ter valor numerico e valor de escolha ao mesmo tempo.')
