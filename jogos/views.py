import json
import logging
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from .models import TipoJogo, Concurso, JogoGerado
from .forms import NovoJogoForm, CadastrarResultadoForm
from .game_engine import gerar_jogo_unico, contar_pares_sequenciais
from . import loteria_service

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """Página inicial com resumo."""
    user = request.user
    total_jogos = JogoGerado.objects.filter(usuario=user).count()
    jogos_pendentes = JogoGerado.objects.filter(usuario=user, conferido=False).count()
    jogos_conferidos = JogoGerado.objects.filter(usuario=user, conferido=True)
    jogos_com_acertos = jogos_conferidos.filter(acertos__gt=0).count()
    ultimos_jogos = JogoGerado.objects.filter(usuario=user).select_related('tipo_jogo')[:5]
    tipos_jogo = TipoJogo.objects.all()

    context = {
        'total_jogos': total_jogos,
        'jogos_pendentes': jogos_pendentes,
        'jogos_com_acertos': jogos_com_acertos,
        'ultimos_jogos': ultimos_jogos,
        'tipos_jogo': tipos_jogo,
    }
    return render(request, 'jogos/dashboard.html', context)


@login_required
def novo_jogo(request):
    """Página para gerar um novo jogo."""
    form = NovoJogoForm()
    tipos_jogo = TipoJogo.objects.all()

    # Dados dos tipos de jogo para o JavaScript (cores, config)
    tipos_data = {}
    for t in tipos_jogo:
        tipos_data[t.id] = {
            'nome': t.nome,
            'cor': t.cor,
            'qtd_dezenas': t.qtd_dezenas,
            'max_numero': t.max_numero,
            'qtd_trevos': t.qtd_trevos,
        }

    context = {
        'form': form,
        'tipos_data_json': json.dumps(tipos_data),
    }
    return render(request, 'jogos/novo_jogo.html', context)


@login_required
@require_POST
def gerar_jogo_api(request):
    """Endpoint AJAX para gerar um jogo."""
    form = NovoJogoForm(request.POST)
    if not form.is_valid():
        return JsonResponse({
            'success': False,
            'errors': form.errors,
        }, status=400)

    tipo_jogo = form.cleaned_data['tipo_jogo']
    numero_concurso = form.cleaned_data['numero_concurso']

    numeros, trevos, foi_repetido = gerar_jogo_unico(tipo_jogo, request.user)

    # Buscar ou criar link com Concurso oficial
    concurso_obj = Concurso.objects.filter(
        tipo_jogo=tipo_jogo, numero=numero_concurso
    ).first()

    # Salvar jogo
    jogo = JogoGerado.objects.create(
        usuario=request.user,
        tipo_jogo=tipo_jogo,
        concurso=concurso_obj,
        numero_concurso=numero_concurso,
        numeros=numeros,
        trevos=trevos,
    )

    pares_seq = contar_pares_sequenciais(numeros)

    return JsonResponse({
        'success': True,
        'jogo_id': jogo.id,
        'numeros': numeros,
        'trevos': trevos,
        'tipo_jogo': tipo_jogo.nome,
        'cor': tipo_jogo.cor,
        'numero_concurso': numero_concurso,
        'pares_sequenciais': pares_seq,
        'foi_repetido': foi_repetido,
        'criado_em': jogo.criado_em.strftime('%d/%m/%Y %H:%M'),
    })


@login_required
def historico(request):
    """Lista de jogos gerados pelo usuário."""
    tipo_filtro = request.GET.get('tipo', '')
    conferido_filtro = request.GET.get('conferido', '')

    jogos = JogoGerado.objects.filter(
        usuario=request.user
    ).select_related('tipo_jogo', 'concurso')

    if tipo_filtro:
        jogos = jogos.filter(tipo_jogo__id=tipo_filtro)
    if conferido_filtro == 'sim':
        jogos = jogos.filter(conferido=True)
    elif conferido_filtro == 'nao':
        jogos = jogos.filter(conferido=False)

    tipos_jogo = TipoJogo.objects.all()

    context = {
        'jogos': jogos,
        'tipos_jogo': tipos_jogo,
        'tipo_filtro': tipo_filtro,
        'conferido_filtro': conferido_filtro,
    }
    return render(request, 'jogos/historico.html', context)


@login_required
def detalhes_jogo(request, jogo_id):
    """Retorna detalhes de um jogo (para modal AJAX)."""
    jogo = get_object_or_404(JogoGerado, id=jogo_id, usuario=request.user)

    data = {
        'id': jogo.id,
        'tipo_jogo': jogo.tipo_jogo.nome,
        'cor': jogo.tipo_jogo.cor,
        'numero_concurso': jogo.numero_concurso,
        'numeros': jogo.numeros,
        'trevos': jogo.trevos,
        'criado_em': jogo.criado_em.strftime('%d/%m/%Y %H:%M'),
        'conferido': jogo.conferido,
        'acertos': jogo.acertos,
        'acertos_segundo_sorteio': jogo.acertos_segundo_sorteio,
        'acertos_trevos': jogo.acertos_trevos,
        'faixa_premio': jogo.faixa_premio,
        'pares_sequenciais': contar_pares_sequenciais(jogo.numeros),
        'aplica_regra_sequencia': jogo.tipo_jogo.aplica_regra_sequencia,
        'tem_segundo_sorteio': jogo.tipo_jogo.tem_segundo_sorteio,
        'qtd_trevos': jogo.tipo_jogo.qtd_trevos,
    }

    # Se conferido e tem concurso, incluir resultado
    if jogo.concurso and jogo.concurso.dezenas:
        data['resultado_oficial'] = {
            'dezenas': jogo.concurso.dezenas,
            'dezenas_segundo_sorteio': jogo.concurso.dezenas_segundo_sorteio,
            'trevos_sorteados': jogo.concurso.trevos_sorteados,
            'data_sorteio': jogo.concurso.data_sorteio.strftime('%d/%m/%Y') if jogo.concurso.data_sorteio else '',
        }

    return JsonResponse(data)


@login_required
@require_POST
def refazer_jogo(request, jogo_id):
    """Gera novo jogo do mesmo tipo e concurso."""
    jogo_original = get_object_or_404(JogoGerado, id=jogo_id, usuario=request.user)

    tipo_jogo = jogo_original.tipo_jogo
    numero_concurso = jogo_original.numero_concurso

    numeros, trevos, foi_repetido = gerar_jogo_unico(tipo_jogo, request.user)

    concurso_obj = Concurso.objects.filter(
        tipo_jogo=tipo_jogo, numero=numero_concurso
    ).first()

    novo_jogo = JogoGerado.objects.create(
        usuario=request.user,
        tipo_jogo=tipo_jogo,
        concurso=concurso_obj,
        numero_concurso=numero_concurso,
        numeros=numeros,
        trevos=trevos,
    )

    return JsonResponse({
        'success': True,
        'jogo_id': novo_jogo.id,
        'numeros': numeros,
        'trevos': trevos,
        'tipo_jogo': tipo_jogo.nome,
        'cor': tipo_jogo.cor,
        'numero_concurso': numero_concurso,
        'pares_sequenciais': contar_pares_sequenciais(numeros),
        'foi_repetido': foi_repetido,
        'criado_em': novo_jogo.criado_em.strftime('%d/%m/%Y %H:%M'),
    })


@login_required
def resultados(request):
    """Área de resultados oficiais."""
    tipo_filtro = request.GET.get('tipo', '')

    concursos = Concurso.objects.select_related('tipo_jogo').all()
    if tipo_filtro:
        concursos = concursos.filter(tipo_jogo__id=tipo_filtro)

    concursos = concursos[:50]  # Limitar exibição
    tipos_jogo = TipoJogo.objects.all()

    context = {
        'concursos': concursos,
        'tipos_jogo': tipos_jogo,
        'tipo_filtro': tipo_filtro,
    }
    return render(request, 'jogos/resultados.html', context)


@login_required
@require_POST
def buscar_resultado_api(request):
    """Busca resultado via API da Caixa (AJAX)."""
    tipo_jogo_id = request.POST.get('tipo_jogo')
    numero_concurso = request.POST.get('numero_concurso')

    if not tipo_jogo_id or not numero_concurso:
        return JsonResponse({'success': False, 'error': 'Campos obrigatórios.'}, status=400)

    try:
        tipo_jogo = TipoJogo.objects.get(id=tipo_jogo_id)
        numero_concurso = int(numero_concurso)
    except (TipoJogo.DoesNotExist, ValueError):
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    # Verificar se já existe no banco
    existente = Concurso.objects.filter(tipo_jogo=tipo_jogo, numero=numero_concurso).first()
    if existente and existente.dezenas:
        return JsonResponse({
            'success': True,
            'source': 'banco',
            'dezenas': existente.dezenas,
            'dezenas_segundo_sorteio': existente.dezenas_segundo_sorteio,
            'trevos_sorteados': existente.trevos_sorteados,
            'data_sorteio': existente.data_sorteio.strftime('%d/%m/%Y') if existente.data_sorteio else '',
        })

    # Buscar na API
    resultado = loteria_service.get_resultado(tipo_jogo.slug_api, numero_concurso)
    if resultado is None:
        return JsonResponse({
            'success': False,
            'error': 'Não foi possível buscar o resultado na API da Caixa. Tente novamente ou cadastre manualmente.',
        })

    # Salvar no banco
    data_sorteio = None
    if resultado['data_sorteio']:
        try:
            data_sorteio = datetime.strptime(resultado['data_sorteio'], '%d/%m/%Y').date()
        except ValueError:
            pass

    concurso_obj, created = Concurso.objects.update_or_create(
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
            'cadastrado_manualmente': False,
        },
    )

    # Vincular jogos existentes
    JogoGerado.objects.filter(
        tipo_jogo=tipo_jogo,
        numero_concurso=numero_concurso,
        concurso__isnull=True,
    ).update(concurso=concurso_obj)

    return JsonResponse({
        'success': True,
        'source': 'api',
        'dezenas': resultado['dezenas'],
        'dezenas_segundo_sorteio': resultado['dezenas_segundo_sorteio'],
        'trevos_sorteados': resultado['trevos_sorteados'],
        'data_sorteio': resultado['data_sorteio'],
    })


@login_required
def cadastrar_resultado(request):
    """Cadastro manual de resultado oficial."""
    if request.method == 'POST':
        form = CadastrarResultadoForm(request.POST)
        if form.is_valid():
            tipo_jogo = form.cleaned_data['tipo_jogo']
            numero = form.cleaned_data['numero_concurso']
            data_sorteio = form.cleaned_data['data_sorteio']
            dezenas = form.cleaned_data['dezenas']
            dezenas_2 = form.cleaned_data['dezenas_segundo_sorteio']
            trevos = form.cleaned_data['trevos']

            concurso_obj, created = Concurso.objects.update_or_create(
                tipo_jogo=tipo_jogo,
                numero=numero,
                defaults={
                    'dezenas': dezenas,
                    'dezenas_segundo_sorteio': dezenas_2,
                    'trevos_sorteados': trevos,
                    'data_sorteio': data_sorteio,
                    'cadastrado_manualmente': True,
                },
            )

            # Vincular jogos existentes
            JogoGerado.objects.filter(
                tipo_jogo=tipo_jogo,
                numero_concurso=numero,
                concurso__isnull=True,
            ).update(concurso=concurso_obj)

            action = 'cadastrado' if created else 'atualizado'
            messages.success(request, f'Resultado do concurso {numero} ({tipo_jogo.nome}) {action} com sucesso.')
            return redirect('jogos:resultados')
    else:
        form = CadastrarResultadoForm()

    return render(request, 'jogos/cadastrar_resultado.html', {'form': form})


@login_required
@require_POST
def conferir_jogo(request, jogo_id):
    """Confere um jogo contra o resultado oficial."""
    jogo = get_object_or_404(JogoGerado, id=jogo_id, usuario=request.user)

    # Buscar resultado oficial
    concurso_obj = jogo.concurso
    if not concurso_obj or not concurso_obj.dezenas:
        # Tentar buscar na API
        resultado = loteria_service.get_resultado(
            jogo.tipo_jogo.slug_api, jogo.numero_concurso
        )
        if resultado and resultado['dezenas']:
            data_sorteio = None
            if resultado['data_sorteio']:
                try:
                    data_sorteio = datetime.strptime(resultado['data_sorteio'], '%d/%m/%Y').date()
                except ValueError:
                    pass

            concurso_obj, _ = Concurso.objects.update_or_create(
                tipo_jogo=jogo.tipo_jogo,
                numero=jogo.numero_concurso,
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
            jogo.concurso = concurso_obj
            jogo.save(update_fields=['concurso'])
        else:
            return JsonResponse({
                'success': False,
                'error': 'Resultado oficial não disponível. Cadastre manualmente ou tente mais tarde.',
            })

    # Conferir
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
    jogo.save()

    return JsonResponse({
        'success': True,
        'acertos': conf['acertos'],
        'acertos_segundo_sorteio': conf['acertos_segundo_sorteio'],
        'acertos_trevos': conf['acertos_trevos'],
        'numeros_acertados': conf['numeros_acertados'],
        'numeros_acertados_segundo': conf['numeros_acertados_segundo'],
        'trevos_acertados': conf['trevos_acertados'],
        'resultado_oficial': concurso_obj.dezenas,
    })
