import random
import re
from decimal import Decimal

import requests

from .models import JogoGerado, JOGOS_CONFIG, JOGOS_COM_REGRA_SEQUENCIA, INTERVALO_MIN_SEQUENCIA, ResultadoLoteria


def normalizar_numeros(numeros):
    """Normaliza entradas em lista de inteiros para uso em validação e tabela."""
    if numeros is None:
        return []
    if isinstance(numeros, str):
        numeros = numeros.replace(' ', '').replace(';', ',').replace('.', ',')
        if ',' in numeros:
            lista = numeros.split(',')
        else:
            lista = [numeros]
        return [int(item) for item in lista if item]
    if isinstance(numeros, (list, tuple, set)):
        return [int(item) for item in numeros]
    return [int(numeros)]


def contar_pares_sequenciais(numeros):
    """Conta quantos pares de numeros consecutivos existem na lista ordenada."""
    if len(numeros) < 2:
        return 0
    pares = 0
    i = 0
    nums_sorted = sorted(numeros)
    while i < len(nums_sorted) - 1:
        if nums_sorted[i + 1] == nums_sorted[i] + 1:
            pares += 1
            i += 2
        else:
            i += 1
    return pares


def ultimos_jogos_tiveram_sequencia(usuario, jogo_nome, intervalo=INTERVALO_MIN_SEQUENCIA):
    """Verifica se nos ultimos N jogos do mesmo tipo houve algum par sequencial."""
    ultimos = JogoGerado.objects.filter(
        usuario=usuario,
        jogo=jogo_nome
    ).order_by('-criado_em')[:intervalo]

    for jogo in ultimos:
        if contar_pares_sequenciais(jogo.numeros) > 0:
            return True
    return False


def gerar_aposta(nome_jogo, usuario=None):
    """Gera uma aposta valida respeitando as regras de sequencia."""
    config = JOGOS_CONFIG.get(nome_jogo)
    if not config:
        return None, None

    aplica_regra_sequencia = nome_jogo in JOGOS_COM_REGRA_SEQUENCIA

    if aplica_regra_sequencia and usuario is not None:
        bloquear_sequencias = ultimos_jogos_tiveram_sequencia(usuario, nome_jogo)
    else:
        bloquear_sequencias = False

    max_tentativas = 10000
    tentativa = 0

    while tentativa < max_tentativas:
        tentativa += 1
        resultado_jogo = []
        while len(resultado_jogo) < config['apostas']:
            numero = random.randint(1, config['numeros'])
            if numero not in resultado_jogo:
                resultado_jogo.append(numero)

        resultado_jogo.sort()

        if aplica_regra_sequencia:
            pares = contar_pares_sequenciais(resultado_jogo)

            if bloquear_sequencias:
                if pares > 0:
                    continue
            else:
                if pares > 1:
                    continue

        break

    resultado_trevos = []
    if config['qtd_trevos'] > 0:
        while len(resultado_trevos) < config['trevos']:
            trevo = random.randint(1, config['qtd_trevos'])
            if trevo not in resultado_trevos:
                resultado_trevos.append(trevo)
        resultado_trevos.sort()

    return resultado_jogo, resultado_trevos


def verificar_jogo_repetido(usuario, jogo_nome, numeros, trevos):
    """Verifica se um jogo identico ja foi gerado pelo usuario."""
    return JogoGerado.objects.filter(
        usuario=usuario,
        jogo=jogo_nome,
        numeros=numeros,
        trevos=trevos if trevos else []
    ).exists()


def calcular_estatisticas(usuario, jogo_nome):
    """Calcula estatisticas para um tipo de jogo especifico."""
    jogos = JogoGerado.objects.filter(usuario=usuario, jogo=jogo_nome)
    total = jogos.count()

    if total == 0:
        return None

    com_sequencia = jogos.filter(pares_sequenciais__gt=0).count()

    frequencia = {}
    for jogo in jogos:
        for num in jogo.numeros:
            frequencia[num] = frequencia.get(num, 0) + 1

    mais_frequentes = sorted(frequencia.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        'total': total,
        'com_sequencia': com_sequencia,
        'sem_sequencia': total - com_sequencia,
        'mais_frequentes': mais_frequentes,
        'percentual_sequencia': (com_sequencia / total * 100) if total > 0 else 0
    }


def calcular_premiacao_jogo(jogo, numeros_usuario, trevos_usuario=None, resultado_oficial=None):
    """Compara o jogo do usuario com o resultado oficial da CEF e informa premio, acertos e status."""
    if resultado_oficial is None:
        return {'ganhou': False, 'acertos': 0, 'valor': 'R$ 0,00', 'categoria': 'Sem resultado'}

    numeros_usuario = set(normalizar_numeros(numeros_usuario))
    numeros_resultado = set(normalizar_numeros(resultado_oficial.get('numeros', [])))
    acertos = len(numeros_usuario & numeros_resultado)

    premio = resultado_oficial.get('premiacoes', {})
    premio_chave = None
    valor = Decimal('0')

    if jogo == 'Mega-sena':
        premio_chave = 'sena' if acertos >= 4 else None
    elif jogo == 'Quina':
        premio_chave = 'quina' if acertos >= 3 else None
    elif jogo == 'Lotofacil':
        premio_chave = 'lotofacil' if acertos >= 11 else None
    elif jogo == 'Lotomania':
        premio_chave = 'lotomania' if acertos >= 0 else 'lotomania'
    elif jogo == 'Milionaria':
        premio_chave = 'milionaria' if acertos >= 4 else None
    elif jogo == 'Dupla-Sena':
        premio_chave = 'dupla_sena' if acertos >= 4 else None

    if premio_chave and isinstance(premio, dict):
        premio_info = premio.get(premio_chave, {})
        valor_raw = premio_info.get('valor', 'R$ 0,00')
        valor_raw = str(valor_raw).replace('R$', '').replace('.', '').replace(',', '.')
        try:
            valor = Decimal(valor_raw.strip())
        except Exception:
            valor = Decimal('0')

    ganhou = bool(premio_chave and acertos > 0 and valor > 0)
    return {
        'ganhou': ganhou,
        'acertos': acertos,
        'valor': f'R$ {valor:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.'),
        'categoria': premio_chave or 'Sem premio',
        'resultado': resultado_oficial,
    }


def capturar_resultado_cef(jogo, concurso):
    """Busca o resultado oficial do jogo e concurso na CEF. Se a pagina da Caixa estiver indisponivel, retorna None."""
    jogo_slug = {
        'Mega-sena': 'mega-sena',
        'Milionaria': 'mais-milionaria',
        'Lotomania': 'lotomania',
        'Lotofacil': 'lotofacil',
        'Quina': 'quina',
        'Dupla-Sena': 'dupla-sena',
    }.get(jogo)

    if not jogo_slug:
        return None

    nome_pagina = jogo_slug.replace('-', ' ').title().replace(' ', '-')
    url = f'https://loterias.caixa.gov.br/Paginas/{nome_pagina}.aspx'
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
    except Exception:
        return None

    html = response.text
    bloco = None
    markers = [
        'Concurso', 'Sorteio', 'Concurso', 'ACUMULOU', 'GANHADOR', 'Trevos sorteados', '1º sorteio', '2º sorteio'
    ]
    for marker in markers:
        idx = html.lower().find(marker.lower())
        if idx != -1:
            bloco = html[idx: idx + 2500]
            break
    if not bloco:
        return None

    numeros = []
    for match in re.findall(r'>(\d{1,2})<', bloco):
        numero = int(match)
        if 1 <= numero <= 100:
            numeros.append(numero)
    numeros = sorted(set(numeros))[:15]
    if not numeros:
        return None

    return {
        'jogo': jogo,
        'concurso': concurso,
        'numeros': numeros,
        'trevos': [],
        'premiacoes': {'sena': {'valor': 'R$ 0,00'}}
    }


def verificar_resultados_usuarios(usuario=None):
    """Valida jogos do usuario contra resultados oficiais da CEF e atualiza o status de premio."""
    queryset = JogoGerado.objects.all()
    if usuario is not None:
        queryset = queryset.filter(usuario=usuario)

    for jogo in queryset:
        if jogo.resultado_verificado:
            continue
        resultado = capturar_resultado_cef(jogo.jogo, jogo.concurso)
        if not resultado:
            continue
        premio = calcular_premiacao_jogo(jogo.jogo, jogo.numeros, jogo.trevos, resultado)
        jogo.resultado_verificado = True
        jogo.acertos = premio['acertos']
        jogo.premio = Decimal(str(premio['valor'].replace('R$ ', '').replace('.', '').replace(',', '.')))
        jogo.premio_descricao = premio['categoria']
        jogo.save(update_fields=['resultado_verificado', 'acertos', 'premio', 'premio_descricao', 'atualizado_em'])

    return True
