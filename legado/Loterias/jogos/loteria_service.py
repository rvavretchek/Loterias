"""
Serviço de integração com a API de Loterias da Caixa.

Endpoint base: https://servicebus2.caixa.gov.br/portaldeloterias/api/{modalidade}/{concurso}

Trata:
- Headers com User-Agent de navegador
- Erros de conexão, 404, 500
- SSL/TLS (verify=False quando necessário)
- Conversão de strings "01" para inteiros
"""
import logging
import requests
import urllib3
from datetime import datetime

logger = logging.getLogger(__name__)

# Desabilitar warnings de SSL quando verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE_URL = 'https://servicebus2.caixa.gov.br/portaldeloterias/api'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Accept': 'application/json',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Referer': 'https://loterias.caixa.gov.br/',
}

# Mapeamento de nomes no sistema → slug da API
MODALIDADE_MAP = {
    'Mega-sena': 'megasena',
    'Lotofácil': 'lotofacil',
    'Lotomania': 'lotomania',
    'Quina': 'quina',
    'Dupla-Sena': 'duplasena',
    'Milionária': 'maismilionaria',
}


def get_resultado(modalidade, concurso):
    """
    Busca resultado oficial de um concurso na API da Caixa.

    Args:
        modalidade: slug da API ('megasena', 'lotofacil', etc.) ou nome do jogo
        concurso: número do concurso (int). Se None, cancela o request.

    Returns:
        dict com chaves:
            - dezenas: list[int]
            - dezenas_segundo_sorteio: list[int] (Dupla-Sena)
            - trevos_sorteados: list[int] (Milionária)
            - data_sorteio: str (dd/mm/yyyy)
            - concurso_numero: int
            - concurso_proximo: int
            - valor_estimado: float
            - dados_completos: dict (resposta completa)
        None se falhar ou concurso for None.
    """
    if concurso is None:
        logger.warning("Concurso é None — request cancelado.")
        return None

    # Converter nome do jogo para slug se necessário
    slug = MODALIDADE_MAP.get(modalidade, modalidade)

    url = f"{API_BASE_URL}/{slug}/{concurso}"
    logger.info(f"Buscando resultado: {url}")

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        response = session.get(url, verify=False, timeout=30)

        if response.status_code == 404:
            logger.warning(f"Concurso {concurso} de {slug} não encontrado (404).")
            return None

        response.raise_for_status()

        data = response.json()

        # Extrair dezenas (converter "01" → 1)
        dezenas = [int(d) for d in data.get('listaDezenas', [])]

        # Dezenas do 2o sorteio (Dupla-Sena)
        dezenas_2 = []
        if data.get('listaDezenasSegundoSorteio'):
            dezenas_2 = [int(d) for d in data['listaDezenasSegundoSorteio']]

        # Trevos (Milionária)
        trevos = []
        if data.get('trevosSorteados'):
            trevos = [int(t) for t in data['trevosSorteados']]

        # Data do sorteio
        data_sorteio = data.get('dataApuracao', '')

        return {
            'dezenas': sorted(dezenas),
            'dezenas_segundo_sorteio': sorted(dezenas_2),
            'trevos_sorteados': sorted(trevos),
            'data_sorteio': data_sorteio,
            'concurso_numero': data.get('numero', concurso),
            'concurso_proximo': data.get('numeroConcursoProximo'),
            'valor_estimado': data.get('valorEstimadoProximoConcurso', 0),
            'dados_completos': data,
        }

    except requests.exceptions.ConnectionError:
        logger.error(f"Erro de conexão ao buscar {url}")
        return None
    except requests.exceptions.Timeout:
        logger.error(f"Timeout ao buscar {url}")
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(f"Erro HTTP {e.response.status_code} ao buscar {url}: {e}")
        return None
    except (ValueError, KeyError) as e:
        logger.error(f"Erro ao processar resposta de {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao buscar {url}: {e}")
        return None


def conferir_jogo(numeros_apostados, dezenas_sorteadas, trevos_apostados=None,
                  trevos_sorteados=None, dezenas_segundo_sorteio=None):
    """
    Confere um jogo contra o resultado oficial usando lógica de conjuntos.

    Args:
        numeros_apostados: list[int]
        dezenas_sorteadas: list[int]
        trevos_apostados: list[int] ou None
        trevos_sorteados: list[int] ou None
        dezenas_segundo_sorteio: list[int] ou None (Dupla-Sena)

    Returns:
        dict com:
            - acertos: int
            - acertos_segundo_sorteio: int ou None
            - acertos_trevos: int ou None
            - numeros_acertados: list[int]
            - numeros_acertados_segundo: list[int] ou None
            - trevos_acertados: list[int] ou None
    """
    set_apostados = set(numeros_apostados)
    set_sorteados = set(dezenas_sorteadas)

    acertados = sorted(set_apostados & set_sorteados)
    acertos = len(acertados)

    resultado = {
        'acertos': acertos,
        'acertos_segundo_sorteio': None,
        'acertos_trevos': None,
        'numeros_acertados': acertados,
        'numeros_acertados_segundo': None,
        'trevos_acertados': None,
    }

    # Dupla-Sena: conferir 2o sorteio
    if dezenas_segundo_sorteio:
        set_segundo = set(dezenas_segundo_sorteio)
        acertados_2 = sorted(set_apostados & set_segundo)
        resultado['acertos_segundo_sorteio'] = len(acertados_2)
        resultado['numeros_acertados_segundo'] = acertados_2

    # Trevos (Milionária)
    if trevos_apostados and trevos_sorteados:
        set_trevos_apost = set(trevos_apostados)
        set_trevos_sort = set(trevos_sorteados)
        trevos_acert = sorted(set_trevos_apost & set_trevos_sort)
        resultado['acertos_trevos'] = len(trevos_acert)
        resultado['trevos_acertados'] = trevos_acert

    return resultado
