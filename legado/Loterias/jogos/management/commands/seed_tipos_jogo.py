"""
Management command: seed_tipos_jogo

Popula a tabela TipoJogo com as configurações de cada modalidade de loteria.

Uso:
    python manage.py seed_tipos_jogo
"""
from django.core.management.base import BaseCommand
from jogos.models import TipoJogo


TIPOS_JOGO = [
    {
        'nome': 'Mega-sena',
        'slug_api': 'megasena',
        'cor': '#209869',
        'qtd_dezenas': 6,
        'max_numero': 60,
        'qtd_trevos': 0,
        'max_trevo': 0,
        'aplica_regra_sequencia': True,
        'tem_segundo_sorteio': False,
    },
    {
        'nome': 'Lotofácil',
        'slug_api': 'lotofacil',
        'cor': '#930089',
        'qtd_dezenas': 15,
        'max_numero': 25,
        'qtd_trevos': 0,
        'max_trevo': 0,
        'aplica_regra_sequencia': False,
        'tem_segundo_sorteio': False,
    },
    {
        'nome': 'Lotomania',
        'slug_api': 'lotomania',
        'cor': '#F78100',
        'qtd_dezenas': 50,
        'max_numero': 100,
        'qtd_trevos': 0,
        'max_trevo': 0,
        'aplica_regra_sequencia': False,
        'tem_segundo_sorteio': False,
    },
    {
        'nome': 'Quina',
        'slug_api': 'quina',
        'cor': '#260085',
        'qtd_dezenas': 5,
        'max_numero': 80,
        'qtd_trevos': 0,
        'max_trevo': 0,
        'aplica_regra_sequencia': True,
        'tem_segundo_sorteio': False,
    },
    {
        'nome': 'Dupla-Sena',
        'slug_api': 'duplasena',
        'cor': '#A61324',
        'qtd_dezenas': 6,
        'max_numero': 50,
        'qtd_trevos': 0,
        'max_trevo': 0,
        'aplica_regra_sequencia': True,
        'tem_segundo_sorteio': True,
    },
    {
        'nome': 'Milionária',
        'slug_api': 'maismilionaria',
        'cor': '#002060',
        'qtd_dezenas': 6,
        'max_numero': 50,
        'qtd_trevos': 2,
        'max_trevo': 6,
        'aplica_regra_sequencia': True,
        'tem_segundo_sorteio': False,
    },
]


class Command(BaseCommand):
    help = 'Popula os tipos de jogo de loteria no banco de dados.'

    def handle(self, *args, **options):
        for data in TIPOS_JOGO:
            obj, created = TipoJogo.objects.update_or_create(
                nome=data['nome'],
                defaults=data,
            )
            status = 'CRIADO' if created else 'ATUALIZADO'
            self.stdout.write(self.style.SUCCESS(
                f'  [{status}] {obj.nome} (API: {obj.slug_api})'
            ))

        self.stdout.write(self.style.SUCCESS(
            f'\nTotal: {TipoJogo.objects.count()} tipos de jogo.'
        ))
