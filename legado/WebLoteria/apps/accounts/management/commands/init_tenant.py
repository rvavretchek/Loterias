from django.core.management.base import BaseCommand
from django.db import connection
from apps.accounts.models import Tenant, Domain


class Command(BaseCommand):
    help = 'Cria o tenant publico inicial'

    def handle(self, *args, **options):
        if Tenant.objects.filter(schema_name='public').exists():
            self.stdout.write(self.style.WARNING('Tenant publico ja existe.'))
            return

        tenant = Tenant.objects.create(
            schema_name='public',
            nome='Public',
            slug='public',
            email='admin@loterias.com'
        )

        Domain.objects.create(
            domain='localhost',
            tenant=tenant,
            is_primary=True
        )

        self.stdout.write(self.style.SUCCESS('Tenant publico criado com sucesso!'))
