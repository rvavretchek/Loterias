from django.core.management.base import BaseCommand

from apps.loterias_core.models import HitNotification


class Command(BaseCommand):
    """Story 2.15: backfill de rollout inicial. Ver deploy/lab/README.md pra quando/como rodar."""

    help = (
        'Marca como lida (is_read=True) toda HitNotification existente no momento da chamada -- '
        'nunca apaga HitNotification/GeneratedBet/LotteryResult, so ajusta o estado de leitura. '
        'Rodar UMA VEZ, logo depois de confirmar que o primeiro ciclo real e nao assistido do cron '
        'terminou, pra evitar que o usuario veja "notificacao nova" de um acerto que ja conhecia via '
        'verificacao sob demanda. Dry-run por padrao -- use --apply pra gravar de verdade.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            default=False,
            help='Grava a mudanca. Sem essa flag, so mostra quantas notificacoes seriam marcadas.',
        )

    def handle(self, *args, **options):
        unread = HitNotification.objects.filter(is_read=False)
        count = unread.count()

        if not options['apply']:
            self.stdout.write(
                f'Dry-run: {count} HitNotification(s) nao lida(s) seriam marcadas como lidas. '
                'Rode de novo com --apply pra gravar.'
            )
            return

        updated = unread.update(is_read=True)
        self.stdout.write(self.style.SUCCESS(f'{updated} HitNotification(s) marcada(s) como lida(s).'))
