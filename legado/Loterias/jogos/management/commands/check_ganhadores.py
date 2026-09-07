"""
Management command: check_ganhadores

Percorre jogos não conferidos no banco de dados, busca resultados oficiais
via API da Caixa, e confere os jogos.

Idempotente — pode ser executado múltiplas vezes sem efeitos colaterais.
Configurado para rodar via cron:
  - 22:00 — primeira tentativa
  - 01:00 — retry (+3h)
  - 07:00 — retry (+9h)

Respeita a feature flag ENABLE_SCHEDULED_TASKS.

Uso:
    python manage.py check_ganhadores
    python manage.py check_ganhadores --tipo megasena
    python manage.py check_ganhadores --concurso 2700
"""
import logging
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from jogos.models import TipoJogo, Concurso, JogoGerado
from jogos import loteria_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Confere jogos salvos contra resultados oficiais da Caixa.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tipo', type=str, default='',
            help='Filtrar por slug da API (ex: megasena, lotofacil)',
        )
        parser.add_argument(
            '--concurso', type=int, default=None,
            help='Filtrar por número de concurso específico',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Ignorar feature flag e executar mesmo se desabilitado',
        )

    def handle(self, *args, **options):
        # Verificar feature flag
        if not options['force'] and not settings.FEATURE_FLAGS.get('ENABLE_SCHEDULED_TASKS', True):
            self.stdout.write(self.style.WARNING(
                'Feature flag ENABLE_SCHEDULED_TASKS está desabilitada. '
                'Use --force para executar mesmo assim.'
            ))
            return

        self.stdout.write(self.style.NOTICE(
            f'[{datetime.now().strftime("%d/%m/%Y %H:%M:%S")}] '
            'Iniciando conferência de jogos...'
        ))

        # Buscar jogos não conferidos
        jogos_query = JogoGerado.objects.filter(conferido=False).select_related(
            'tipo_jogo', 'concurso', 'usuario'
        )

        if options['tipo']:
            jogos_query = jogos_query.filter(tipo_jogo__slug_api=options['tipo'])
        if options['concurso']:
            jogos_query = jogos_query.filter(numero_concurso=options['concurso'])

        jogos_pendentes = list(jogos_query)

        if not jogos_pendentes:
            self.stdout.write(self.style.SUCCESS('Nenhum jogo pendente de conferência.'))
            return

        self.stdout.write(f'Encontrados {len(jogos_pendentes)} jogos pendentes.')

        # Agrupar por (tipo_jogo, numero_concurso) para otimizar chamadas à API
        concursos_unicos = {}
        for jogo in jogos_pendentes:
            key = (jogo.tipo_jogo_id, jogo.numero_concurso)
            if key not in concursos_unicos:
                concursos_unicos[key] = {
                    'tipo_jogo': jogo.tipo_jogo,
                    'numero': jogo.numero_concurso,
                    'jogos': [],
                }
            concursos_unicos[key]['jogos'].append(jogo)

        total_conferidos = 0
        total_erros = 0
        total_acertos = 0

        for key, info in concursos_unicos.items():
            tipo_jogo = info['tipo_jogo']
            numero = info['numero']
            jogos = info['jogos']

            self.stdout.write(f'\n--- {tipo_jogo.nome} — Concurso {numero} ---')

            # Buscar resultado oficial (do banco ou API)
            concurso_obj = self._obter_resultado(tipo_jogo, numero)

            if concurso_obj is None or not concurso_obj.dezenas:
                self.stdout.write(self.style.WARNING(
                    f'  Resultado não disponível para {tipo_jogo.nome} #{numero}. '
                    'Será tentado novamente na próxima execução.'
                ))
                total_erros += len(jogos)
                continue

            self.stdout.write(
                f'  Dezenas: {", ".join(f"{d:02d}" for d in concurso_obj.dezenas)}'
            )

            # Conferir cada jogo
            for jogo in jogos:
                conf = loteria_service.conferir_jogo(
                    numeros_apostados=jogo.numeros,
                    dezenas_sorteadas=concurso_obj.dezenas,
                    trevos_apostados=jogo.trevos if jogo.trevos else None,
                    trevos_sorteados=concurso_obj.trevos_sorteados if concurso_obj.trevos_sorteados else None,
                    dezenas_segundo_sorteio=concurso_obj.dezenas_segundo_sorteio if concurso_obj.dezenas_segundo_sorteio else None,
                )

                jogo.acertos = conf['acertos']
                jogo.acertos_segundo_sorteio = conf['acertos_segundo_sorteio']
                jogo.acertos_trevos = conf['acertos_trevos']
                jogo.conferido = True
                jogo.concurso = concurso_obj
                jogo.save()

                total_conferidos += 1
                if conf['acertos'] > 0:
                    total_acertos += 1

                acertos_info = f"{conf['acertos']} acertos"
                if conf['acertos_segundo_sorteio'] is not None:
                    acertos_info += f" | 2o sorteio: {conf['acertos_segundo_sorteio']}"
                if conf['acertos_trevos'] is not None:
                    acertos_info += f" | trevos: {conf['acertos_trevos']}"

                estilo = self.style.SUCCESS if conf['acertos'] >= 3 else self.style.NOTICE
                self.stdout.write(estilo(
                    f'  [{jogo.usuario.email}] {acertos_info}'
                ))

        # Resumo
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS(
            f'Conferência concluída: '
            f'{total_conferidos} conferidos, '
            f'{total_acertos} com acertos, '
            f'{total_erros} sem resultado disponível.'
        ))

    def _obter_resultado(self, tipo_jogo, numero_concurso):
        """Busca resultado oficial: primeiro no banco, depois na API."""
        concurso = Concurso.objects.filter(
            tipo_jogo=tipo_jogo, numero=numero_concurso
        ).first()

        if concurso and concurso.dezenas:
            self.stdout.write(f'  [banco] Resultado já cadastrado.')
            return concurso

        # Verificar feature flag de API
        if not settings.FEATURE_FLAGS.get('ENABLE_API_FETCH', True):
            self.stdout.write(self.style.WARNING('  API fetch desabilitada por feature flag.'))
            return None

        # Buscar na API
        self.stdout.write(f'  [api] Buscando resultado na Caixa...')
        resultado = loteria_service.get_resultado(tipo_jogo.slug_api, numero_concurso)

        if resultado is None:
            return None

        data_sorteio = None
        if resultado['data_sorteio']:
            try:
                data_sorteio = datetime.strptime(resultado['data_sorteio'], '%d/%m/%Y').date()
            except ValueError:
                pass

        concurso, created = Concurso.objects.update_or_create(
            tipo_jogo=tipo_jogo,
            numero=numero_concurso,
            defaults={
                'dezenas': resultado['dezenas'],
                'dezenas_segundo_sorteio': resultado['dezenas_segundo_sorteio'],
                'trevos_sorteados': resultado['trevos_sorteados'],
                'data_sorteio': data_sorteio,
                'valor_estimado_proximo': resultado.get('valor_estimado'),
                'proximo_concurso': resultado.get('concurso_proximo'),
                'dados_completos': resultado['dados_completos'],
            },
        )

        status = 'novo' if created else 'atualizado'
        self.stdout.write(self.style.SUCCESS(f'  Resultado {status} no banco.'))
        return concurso
