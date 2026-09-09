from django.core.management.base import BaseCommand

from apps.loterias_core.jobs import update_monthly_prize_values


class Command(BaseCommand):
    help = 'Captura as faixas de premiacao vigentes por Jogo/quantidade de acertos (PrizeTier).'

    def handle(self, *args, **options):
        update_monthly_prize_values()
