from django.core.management.base import BaseCommand

from apps.loterias_core.jobs import fetch_daily_results


class Command(BaseCommand):
    help = 'Captura resultados oficiais pendentes pra todo par Jogo/Concurso em aberto.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--final',
            action='store_true',
            default=False,
            help='Marca esta chamada como a ultima tentativa do dia (usado pela Story 2.9).',
        )

    def handle(self, *args, **options):
        fetch_daily_results(final=options['final'])
