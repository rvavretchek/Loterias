from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Count
from .models import JogoGerado, ResultadoLoteria, JOGOS_CONFIG, JOGOS_COM_REGRA_SEQUENCIA
from .utils import (
    gerar_aposta, verificar_jogo_repetido, contar_pares_sequenciais,
    calcular_estatisticas, normalizar_numeros, calcular_premiacao_jogo,
    capturar_resultado_cef
)


def home(request):
    """Pagina inicial com dashboard."""
    if request.user.is_authenticated:
        total_jogos = JogoGerado.objects.filter(usuario=request.user).count()
        jogos_por_tipo = JogoGerado.objects.filter(usuario=request.user).values('jogo').annotate(
            total=Count('id')
        ).order_by('-total')

        ultimos_jogos = JogoGerado.objects.filter(usuario=request.user)[:10]

        context = {
            'total_jogos': total_jogos,
            'jogos_por_tipo': jogos_por_tipo,
            'ultimos_jogos': ultimos_jogos,
            'jogos_disponiveis': JOGOS_CONFIG,
        }
    else:
        context = {
            'jogos_disponiveis': JOGOS_CONFIG,
        }

    return render(request, 'loterias_core/home.html', context)


@login_required
def gerar_jogo(request):
    """View para gerar novo jogo."""
    if request.method != 'POST':
        return redirect('home')

    jogo_sel = request.POST.get('jogo')
    concurso = request.POST.get('concurso', '').strip()

    if not jogo_sel or not concurso:
        messages.error(request, 'Selecione o jogo e informe o numero do concurso.')
        return redirect('home')

    if jogo_sel not in JOGOS_CONFIG:
        messages.error(request, 'Jogo invalido.')
        return redirect('home')

    # Verificar se concurso ja existe para este usuario e jogo
    if JogoGerado.objects.filter(usuario=request.user, jogo=jogo_sel, concurso=concurso).exists():
        messages.warning(request, f'Ja existe um jogo de {jogo_sel} para o concurso {concurso}.')

    tentativas = 0
    max_tentativas = 1000
    novo_jogo = None
    novos_trevos = None

    while tentativas < max_tentativas:
        nums, trevos = gerar_aposta(jogo_sel, request.user)

        if verificar_jogo_repetido(request.user, jogo_sel, nums, trevos):
            tentativas += 1
            continue

        novo_jogo = nums
        novos_trevos = trevos
        break

    if not novo_jogo:
        messages.warning(request, 'Nao foi possivel gerar um jogo unico apos muitas tentativas.')
        return redirect('home')

    # Calcular pares sequenciais
    pares_seq = contar_pares_sequenciais(novo_jogo)

    # Salvar no banco de dados
    jogo = JogoGerado.objects.create(
        usuario=request.user,
        jogo=jogo_sel,
        concurso=concurso,
        numeros=novo_jogo,
        trevos=novos_trevos if novos_trevos else [],
        pares_sequenciais=pares_seq
    )

    messages.success(request, f'Jogo de {jogo_sel} gerado com sucesso para o concurso {concurso}!')

    return redirect('detalhes_jogo', pk=jogo.pk)


@login_required
def detalhes_jogo(request, pk):
    """Pagina de detalhes de um jogo."""
    jogo = get_object_or_404(JogoGerado, pk=pk, usuario=request.user)

    jogos_anteriores = JogoGerado.objects.filter(
        usuario=request.user,
        jogo=jogo.jogo
    ).exclude(pk=pk).order_by('-criado_em')[:5]

    resultado_oficial = ResultadoLoteria.objects.filter(jogo=jogo.jogo, concurso=jogo.concurso).first()
    premio_info = None
    if resultado_oficial:
        premio_info = calcular_premiacao_jogo(
            jogo.jogo,
            jogo.numeros,
            jogo.trevos,
            {
                'numeros': resultado_oficial.numeros,
                'trevos': resultado_oficial.trevos,
                'premiacoes': resultado_oficial.premiacoes,
            }
        )

    context = {
        'jogo': jogo,
        'jogos_anteriores': jogos_anteriores,
        'aplica_regra_sequencia': jogo.jogo in JOGOS_COM_REGRA_SEQUENCIA,
        'resultado_oficial': resultado_oficial,
        'premio_info': premio_info,
    }

    return render(request, 'loterias_core/detalhes_jogo.html', context)


@login_required
def historico(request):
    """Pagina de historico de jogos."""
    jogos_list = JogoGerado.objects.filter(usuario=request.user)

    jogo_filtro = request.GET.get('jogo')
    if jogo_filtro and jogo_filtro in JOGOS_CONFIG:
        jogos_list = jogos_list.filter(jogo=jogo_filtro)

    ordenacao = request.GET.get('ordenacao', '-criado_em')
    jogos_list = jogos_list.order_by(ordenacao)

    paginator = Paginator(jogos_list, 20)
    page_number = request.GET.get('page')
    jogos = paginator.get_page(page_number)

    context = {
        'jogos': jogos,
        'jogos_disponiveis': JOGOS_CONFIG,
        'jogo_filtro': jogo_filtro,
        'ordenacao': ordenacao,
    }

    return render(request, 'loterias_core/historico.html', context)


@login_required
@require_POST
def salvar_jogo_manual(request):
    """Salva um jogo manual informado pelo usuario."""
    jogo_sel = request.POST.get('jogo')
    concurso = request.POST.get('concurso', '').strip()
    numeros_raw = request.POST.get('numeros', '').strip()

    if not jogo_sel or not concurso or not numeros_raw:
        messages.error(request, 'Preencha o jogo, concurso e numeracao do jogo manual.')
        return redirect('home')

    if jogo_sel not in JOGOS_CONFIG:
        messages.error(request, 'Jogo invalido.')
        return redirect('home')

    numeros = sorted(normalizar_numeros(numeros_raw))
    config = JOGOS_CONFIG[jogo_sel]
    esperado = config['apostas']

    if len(numeros) != esperado:
        messages.error(request, f'Este jogo exige {esperado} numeros. Voce informou {len(numeros)}.')
        return redirect('home')

    minimo = 1
    maximo = config['numeros']
    if any(num < minimo or num > maximo for num in numeros):
        messages.error(request, f'Os numeros devem estar entre {minimo} e {maximo} para {jogo_sel}.')
        return redirect('home')

    if JogoGerado.objects.filter(usuario=request.user, jogo=jogo_sel, concurso=concurso).exists():
        messages.warning(request, f'Ja existe um jogo de {jogo_sel} para o concurso {concurso}.')

    pares_seq = contar_pares_sequenciais(numeros)
    jogo = JogoGerado.objects.create(
        usuario=request.user,
        jogo=jogo_sel,
        concurso=concurso,
        numeros=numeros,
        trevos=[],
        pares_sequenciais=pares_seq,
        manual=True,
    )

    resultado = capturar_resultado_cef(jogo_sel, concurso)
    if resultado:
        ResultadoLoteria.objects.update_or_create(
            jogo=jogo_sel,
            concurso=concurso,
            defaults={
                'numeros': resultado.get('numeros', []),
                'trevos': resultado.get('trevos', []),
                'premiacoes': resultado.get('premiacoes', {}),
                'origem': 'CEF',
            }
        )
        premio = calcular_premiacao_jogo(jogo_sel, jogo.numeros, jogo.trevos, resultado)
        jogo.resultado_verificado = True
        jogo.acertos = premio['acertos']
        jogo.premio = Decimal(str(premio['valor'].replace('R$ ', '').replace('.', '').replace(',', '.')))
        jogo.premio_descricao = premio['categoria']
        jogo.save(update_fields=['resultado_verificado', 'acertos', 'premio', 'premio_descricao', 'atualizado_em'])
        if premio['ganhou']:
            messages.success(request, f'Jogo manual salvo e verificado com {premio["acertos"]} acertos. Premio: {premio["valor"]}.')
        else:
            messages.info(request, f'Jogo manual salvo. Resultado oficial consultado; sem premio para este jogo e concurso.')
    else:
        messages.success(request, f'Jogo manual salvo com sucesso para o concurso {concurso}.')

    return redirect('detalhes_jogo', pk=jogo.pk)


@login_required
def verificar_resultado_jogo(request, pk):
    """Consulta o resultado oficial da CEF para um jogo do usuario e atualiza premio."""
    jogo = get_object_or_404(JogoGerado, pk=pk, usuario=request.user)
    resultado = capturar_resultado_cef(jogo.jogo, jogo.concurso)

    if not resultado:
        messages.warning(request, 'Nao foi possivel consultar o resultado oficial da CEF neste momento.')
        return redirect('detalhes_jogo', pk=pk)

    ResultadoLoteria.objects.update_or_create(
        jogo=jogo.jogo,
        concurso=jogo.concurso,
        defaults={
            'numeros': resultado.get('numeros', []),
            'trevos': resultado.get('trevos', []),
            'premiacoes': resultado.get('premiacoes', {}),
            'origem': 'CEF',
        }
    )

    premio = calcular_premiacao_jogo(jogo.jogo, jogo.numeros, jogo.trevos, resultado)
    jogo.resultado_verificado = True
    jogo.acertos = premio['acertos']
    jogo.premio = Decimal(str(premio['valor'].replace('R$ ', '').replace('.', '').replace(',', '.')))
    jogo.premio_descricao = premio['categoria']
    jogo.save(update_fields=['resultado_verificado', 'acertos', 'premio', 'premio_descricao', 'atualizado_em'])

    if premio['ganhou']:
        messages.success(request, f'Verificacao concluida: {premio["acertos"]} acertos e premio de {premio["valor"]}.')
    else:
        messages.info(request, f'Verificacao concluida: {premio["acertos"]} acertos. Sem premio identificado para este concurso.')

    return redirect('detalhes_jogo', pk=pk)


@login_required
def refazer_jogo(request, pk):
    """Refaz um jogo existente gerando novos numeros."""
    jogo_original = get_object_or_404(JogoGerado, pk=pk, usuario=request.user)

    tentativas = 0
    max_tentativas = 1000
    novo_jogo = None
    novos_trevos = None

    while tentativas < max_tentativas:
        nums, trevos = gerar_aposta(jogo_original.jogo, request.user)

        if verificar_jogo_repetido(request.user, jogo_original.jogo, nums, trevos):
            tentativas += 1
            continue

        novo_jogo = nums
        novos_trevos = trevos
        break

    if not novo_jogo:
        messages.warning(request, 'Nao foi possivel gerar um jogo unico.')
        return redirect('detalhes_jogo', pk=pk)

    pares_seq = contar_pares_sequenciais(novo_jogo)

    # Criar novo jogo baseado no original
    novo_registro = JogoGerado.objects.create(
        usuario=request.user,
        jogo=jogo_original.jogo,
        concurso=jogo_original.concurso,
        numeros=novo_jogo,
        trevos=novos_trevos if novos_trevos else [],
        pares_sequenciais=pares_seq
    )

    messages.success(request, f'Novo jogo de {jogo_original.jogo} gerado com sucesso!')
    return redirect('detalhes_jogo', pk=novo_registro.pk)


@login_required
def estatisticas(request):
    """Pagina de estatisticas do usuario."""
    estatisticas_por_jogo = {}

    for jogo_nome in JOGOS_CONFIG.keys():
        stats = calcular_estatisticas(request.user, jogo_nome)
        if stats:
            estatisticas_por_jogo[jogo_nome] = stats

    # Estatisticas gerais
    total_geral = JogoGerado.objects.filter(usuario=request.user).count()

    context = {
        'estatisticas': estatisticas_por_jogo,
        'total_geral': total_geral,
        'jogos_disponiveis': JOGOS_CONFIG,
    }

    return render(request, 'loterias_core/estatisticas.html', context)


@login_required
@require_POST
def excluir_jogo(request, pk):
    """Exclui um jogo do historico."""
    jogo = get_object_or_404(JogoGerado, pk=pk, usuario=request.user)
    jogo.delete()
    messages.success(request, 'Jogo excluido com sucesso!')
    return redirect('historico')


@login_required
def api_gerar_jogo(request):
    """API endpoint para gerar jogo via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo nao permitido'}, status=405)

    import json
    data = json.loads(request.body)
    jogo_sel = data.get('jogo')
    concurso = data.get('concurso', '').strip()

    if not jogo_sel or not concurso:
        return JsonResponse({'error': 'Dados incompletos'}, status=400)

    nums, trevos = gerar_aposta(jogo_sel, request.user)
    pares_seq = contar_pares_sequenciais(nums)

    # Verificar repeticao
    repetido = verificar_jogo_repetido(request.user, jogo_sel, nums, trevos)

    return JsonResponse({
        'numeros': nums,
        'trevos': trevos,
        'pares_sequenciais': pares_seq,
        'repetido': repetido,
    })
