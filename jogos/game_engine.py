"""
Motor de geração de apostas de loteria.

Migrado da versão Tkinter original, adaptado para uso com models Django.
"""
import random
from .models import TipoJogo, JogoGerado

# Jogos com regra de sequência (máx 1 par por jogo, intervalo mín. de 5 jogos)
INTERVALO_MIN_SEQUENCIA = 5


def contar_pares_sequenciais(numeros):
    """
    Conta quantos pares de números consecutivos existem na lista.
    Ex: [1, 2, 10, 11, 30, 40] → 2 pares (1-2 e 10-11)
    """
    if len(numeros) < 2:
        return 0
    pares = 0
    i = 0
    nums_sorted = sorted(numeros)
    while i < len(nums_sorted) - 1:
        if nums_sorted[i + 1] == nums_sorted[i] + 1:
            pares += 1
            i += 2  # Pula o próximo para não contar triplas como 2 pares
        else:
            i += 1
    return pares


def ultimos_jogos_tiveram_sequencia(tipo_jogo, usuario, intervalo=INTERVALO_MIN_SEQUENCIA):
    """
    Verifica se nos últimos N jogos do mesmo tipo (do mesmo usuário)
    houve algum par sequencial.
    """
    ultimos = JogoGerado.objects.filter(
        usuario=usuario,
        tipo_jogo=tipo_jogo,
    ).order_by('-criado_em')[:intervalo]

    for jogo in ultimos:
        if contar_pares_sequenciais(jogo.numeros) > 0:
            return True
    return False


def gerar_aposta(tipo_jogo, usuario=None):
    """
    Gera uma aposta aleatória respeitando as regras de sequência.

    Args:
        tipo_jogo: instância de TipoJogo
        usuario: instância de CustomUser (para verificar histórico de sequências)

    Returns:
        tuple: (numeros: list[int], trevos: list[int])
    """
    aplica_regra = tipo_jogo.aplica_regra_sequencia

    # Verificar se deve bloquear sequências
    bloquear_sequencias = False
    if aplica_regra and usuario is not None:
        bloquear_sequencias = ultimos_jogos_tiveram_sequencia(tipo_jogo, usuario)

    max_tentativas = 10000
    tentativa = 0

    while tentativa < max_tentativas:
        tentativa += 1

        # Gerar números aleatórios
        resultado = random.sample(range(1, tipo_jogo.max_numero + 1), tipo_jogo.qtd_dezenas)
        resultado.sort()

        if aplica_regra:
            pares = contar_pares_sequenciais(resultado)
            if bloquear_sequencias and pares > 0:
                continue
            if not bloquear_sequencias and pares > 1:
                continue

        break

    # Gerar trevos (para Milionária)
    trevos = []
    if tipo_jogo.qtd_trevos > 0:
        trevos = random.sample(range(1, tipo_jogo.max_trevo + 1), tipo_jogo.qtd_trevos)
        trevos.sort()

    return resultado, trevos


def verificar_jogo_repetido(tipo_jogo, usuario, numeros, trevos):
    """
    Verifica se o jogo já existe no histórico do usuário.
    """
    jogos_existentes = JogoGerado.objects.filter(
        usuario=usuario,
        tipo_jogo=tipo_jogo,
        numeros=numeros,
    )
    if trevos:
        jogos_existentes = jogos_existentes.filter(trevos=trevos)

    return jogos_existentes.exists()


def gerar_jogo_unico(tipo_jogo, usuario, max_tentativas=1000):
    """
    Gera um jogo que não seja repetido no histórico do usuário.

    Returns:
        tuple: (numeros, trevos, foi_repetido)
        foi_repetido indica se após todas as tentativas ainda é repetido.
    """
    for _ in range(max_tentativas):
        numeros, trevos = gerar_aposta(tipo_jogo, usuario)
        if not verificar_jogo_repetido(tipo_jogo, usuario, numeros, trevos):
            return numeros, trevos, False

    # Última tentativa — retorna mesmo repetido
    numeros, trevos = gerar_aposta(tipo_jogo, usuario)
    return numeros, trevos, True
