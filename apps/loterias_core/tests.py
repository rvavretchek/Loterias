import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.loterias_core.models import GeneratedBet, LotteryResult, GAMES_CONFIG
from apps.loterias_core.utils import (
    calcular_estatisticas,
    calcular_premiacao_jogo,
    capturar_resultado_cef,
    contar_pares_sequenciais,
    gerar_aposta,
    normalizar_numeros,
    verificar_jogo_repetido,
)


class NormalizarNumerosTests(TestCase):
    def test_aceita_string_separada_por_virgula(self):
        self.assertEqual(normalizar_numeros('1, 2, 3, 4, 5, 6'), [1, 2, 3, 4, 5, 6])

    def test_aceita_string_separada_por_ponto_e_virgula(self):
        self.assertEqual(normalizar_numeros('1;2;3'), [1, 2, 3])

    def test_aceita_lista(self):
        self.assertEqual(normalizar_numeros([1, 2, 3, 4]), [1, 2, 3, 4])

    def test_aceita_inteiro_unico(self):
        self.assertEqual(normalizar_numeros(7), [7])

    def test_none_retorna_lista_vazia(self):
        self.assertEqual(normalizar_numeros(None), [])

    def test_string_vazia_retorna_lista_vazia(self):
        self.assertEqual(normalizar_numeros(''), [])


class ContarParesSequenciaisTests(TestCase):
    def test_lista_vazia_sem_pares(self):
        self.assertEqual(contar_pares_sequenciais([]), 0)

    def test_lista_com_um_elemento_sem_pares(self):
        self.assertEqual(contar_pares_sequenciais([5]), 0)

    def test_sem_numeros_consecutivos(self):
        self.assertEqual(contar_pares_sequenciais([1, 5, 10, 20]), 0)

    def test_um_par_consecutivo(self):
        self.assertEqual(contar_pares_sequenciais([1, 5, 10, 11]), 1)

    def test_dois_pares_consecutivos_nao_sobrepostos(self):
        self.assertEqual(contar_pares_sequenciais([1, 2, 10, 11]), 2)

    def test_ordena_antes_de_contar(self):
        self.assertEqual(contar_pares_sequenciais([11, 1, 10, 2]), 2)

    def test_tres_consecutivos_conta_um_par_e_sobra_um(self):
        # 1,2,3 -> par (1,2) consumido, 3 fica isolado
        self.assertEqual(contar_pares_sequenciais([1, 2, 3]), 1)


class GerarApostaTests(TestCase):
    def test_jogo_invalido_retorna_none(self):
        nums, trevos = gerar_aposta('Jogo-Inexistente')
        self.assertIsNone(nums)
        self.assertIsNone(trevos)

    def test_mega_sena_gera_quantidade_e_intervalo_corretos(self):
        for _ in range(20):
            nums, trevos = gerar_aposta('Mega-sena')
            self.assertEqual(len(nums), 6)
            self.assertEqual(len(set(nums)), 6, 'numeros nao podem se repetir')
            self.assertTrue(all(1 <= n <= 60 for n in nums))
            self.assertEqual(trevos, [])

    def test_milionaria_gera_numeros_e_trevos(self):
        for _ in range(20):
            nums, trevos = gerar_aposta('Milionaria')
            self.assertEqual(len(nums), 6)
            self.assertTrue(all(1 <= n <= 50 for n in nums))
            self.assertEqual(len(trevos), 2)
            self.assertEqual(len(set(trevos)), 2)
            self.assertTrue(all(1 <= t <= 6 for t in trevos))

    def test_lotomania_gera_50_numeros_ate_100(self):
        nums, trevos = gerar_aposta('Lotomania')
        self.assertEqual(len(nums), 50)
        self.assertTrue(all(1 <= n <= 100 for n in nums))

    def test_numeros_gerados_sempre_ordenados(self):
        for _ in range(10):
            nums, _ = gerar_aposta('Quina')
            self.assertEqual(nums, sorted(nums))

    def test_bloqueia_sequencia_apos_historico_recente_com_par(self):
        usuario = User.objects.create_user(email='seq@example.com', password='SenhaForte123')
        GeneratedBet.objects.create(
            user=usuario, game='Mega-sena', contest='1',
            numbers=[1, 2, 10, 20, 30, 40], clovers=[], sequential_pairs=1,
        )
        for _ in range(30):
            nums, _ = gerar_aposta('Mega-sena', usuario)
            self.assertEqual(contar_pares_sequenciais(nums), 0)


class VerificarJogoRepetidoTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(email='rep@example.com', password='SenhaForte123')

    def test_jogo_nao_existente_nao_e_repetido(self):
        self.assertFalse(
            verificar_jogo_repetido(self.usuario, 'Mega-sena', [1, 2, 3, 4, 5, 6], [])
        )

    def test_jogo_identico_e_repetido(self):
        GeneratedBet.objects.create(
            user=self.usuario, game='Mega-sena', contest='100',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=2,
        )
        self.assertTrue(
            verificar_jogo_repetido(self.usuario, 'Mega-sena', [1, 2, 3, 4, 5, 6], [])
        )


class CalcularEstatisticasTests(TestCase):
    def test_sem_jogos_retorna_none(self):
        usuario = User.objects.create_user(email='stats1@example.com', password='SenhaForte123')
        self.assertIsNone(calcular_estatisticas(usuario, 'Mega-sena'))

    def test_calcula_totais_e_frequencia(self):
        usuario = User.objects.create_user(email='stats2@example.com', password='SenhaForte123')
        GeneratedBet.objects.create(
            user=usuario, game='Mega-sena', contest='1',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=1,
        )
        GeneratedBet.objects.create(
            user=usuario, game='Mega-sena', contest='2',
            numbers=[1, 2, 7, 8, 9, 10], clovers=[], sequential_pairs=0,
        )
        stats = calcular_estatisticas(usuario, 'Mega-sena')
        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['com_sequencia'], 1)
        self.assertEqual(stats['sem_sequencia'], 1)
        frequencia = dict(stats['mais_frequentes'])
        self.assertEqual(frequencia[1], 2)
        self.assertEqual(frequencia[2], 2)


class CalcularPremiacaoJogoTests(TestCase):
    def test_sem_resultado_oficial_nao_ganha(self):
        premio = calcular_premiacao_jogo('Mega-sena', [1, 2, 3, 4, 5, 6], [], None)
        self.assertFalse(premio['ganhou'])
        self.assertEqual(premio['acertos'], 0)
        self.assertEqual(premio['categoria'], 'Sem resultado')

    def test_mega_sena_com_seis_acertos_ganha(self):
        resultado = {
            'numeros': [1, 2, 3, 4, 5, 6],
            'trevos': [],
            'premiacoes': {'sena': {'valor': 'R$ 500.000,00'}},
        }
        premio = calcular_premiacao_jogo('Mega-sena', [1, 2, 3, 4, 5, 6], [], resultado)
        self.assertTrue(premio['ganhou'])
        self.assertEqual(premio['acertos'], 6)
        self.assertIn('R$', premio['valor'])

    def test_mega_sena_com_tres_acertos_nao_ganha(self):
        resultado = {
            'numeros': [1, 2, 3, 40, 50, 60],
            'trevos': [],
            'premiacoes': {'sena': {'valor': 'R$ 500.000,00'}},
        }
        premio = calcular_premiacao_jogo('Mega-sena', [1, 2, 3, 4, 5, 6], [], resultado)
        self.assertFalse(premio['ganhou'])
        self.assertEqual(premio['acertos'], 3)
        self.assertEqual(premio['categoria'], 'Sem premio')

    def test_premiacao_ausente_para_faixa_nao_gera_erro(self):
        resultado = {'numeros': [1, 2, 3, 4, 5, 6], 'trevos': [], 'premiacoes': {}}
        premio = calcular_premiacao_jogo('Mega-sena', [1, 2, 3, 4, 5, 6], [], resultado)
        self.assertFalse(premio['ganhou'])
        self.assertEqual(premio['valor'], 'R$ 0,00')


class CapturarResultadoCefTests(TestCase):
    """capturar_resultado_cef faz scraping externo -- sempre mockar requests.get."""

    def test_jogo_desconhecido_retorna_none(self):
        self.assertIsNone(capturar_resultado_cef('Jogo-Inexistente', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_erro_de_rede_retorna_none_sem_levantar_excecao(self, mock_get):
        mock_get.side_effect = Exception('timeout')
        self.assertIsNone(capturar_resultado_cef('Mega-sena', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_pagina_sem_numeros_reconheciveis_retorna_none(self, mock_get):
        mock_response = Mock()
        mock_response.text = '<html><body>Sem concurso hoje</body></html>'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        self.assertIsNone(capturar_resultado_cef('Mega-sena', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_pagina_com_numeros_retorna_resultado(self, mock_get):
        html = 'Concurso ' + ''.join(f'>{n}<' for n in [4, 8, 15, 16, 23, 42])
        mock_response = Mock()
        mock_response.text = html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        resultado = capturar_resultado_cef('Mega-sena', '2500')
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado['jogo'], 'Mega-sena')
        self.assertEqual(resultado['numeros'], [4, 8, 15, 16, 23, 42])


class GerarJogoViewTests(TestCase):
    """Regressao direta do bug documentado em docs/diagnostico-projeto.md:
    gerar um jogo salvo no banco parava de funcionar com a multitenancy."""

    def setUp(self):
        self.usuario = User.objects.create_user(email='view@example.com', password='SenhaForte123')
        self.client.force_login(self.usuario)

    def test_gerar_jogo_cria_registro_no_banco(self):
        response = self.client.post(reverse('gerar_jogo'), {'jogo': 'Mega-sena', 'concurso': '2500'})
        self.assertEqual(GeneratedBet.objects.filter(user=self.usuario).count(), 1)
        jogo = GeneratedBet.objects.get(user=self.usuario)
        self.assertEqual(len(jogo.numbers), GAMES_CONFIG['Mega-sena']['bets_count'])
        self.assertRedirects(response, reverse('detalhes_jogo', args=[jogo.pk]))

    def test_gerar_jogo_exige_login(self):
        self.client.logout()
        response = self.client.post(reverse('gerar_jogo'), {'jogo': 'Mega-sena', 'concurso': '2500'})
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(GeneratedBet.objects.count(), 0)

    def test_gerar_jogo_sem_concurso_nao_cria_registro(self):
        self.client.post(reverse('gerar_jogo'), {'jogo': 'Mega-sena', 'concurso': ''})
        self.assertEqual(GeneratedBet.objects.count(), 0)

    def test_gerar_jogo_invalido_nao_cria_registro(self):
        self.client.post(reverse('gerar_jogo'), {'jogo': 'Nao-Existe', 'concurso': '2500'})
        self.assertEqual(GeneratedBet.objects.count(), 0)

    def test_api_gerar_jogo_retorna_json(self):
        response = self.client.post(
            reverse('api_gerar_jogo'),
            data=json.dumps({'jogo': 'Quina', 'concurso': '2500'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['numeros']), GAMES_CONFIG['Quina']['bets_count'])


class HistoricoViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(email='hist@example.com', password='SenhaForte123')
        self.outro_usuario = User.objects.create_user(email='outro@example.com', password='SenhaForte123')
        self.client.force_login(self.usuario)

    def test_historico_mostra_apenas_jogos_do_usuario_logado(self):
        GeneratedBet.objects.create(
            user=self.usuario, game='Mega-sena', contest='1',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        GeneratedBet.objects.create(
            user=self.outro_usuario, game='Mega-sena', contest='1',
            numbers=[10, 20, 30, 40, 50, 60], clovers=[], sequential_pairs=0,
        )
        response = self.client.get(reverse('historico'))
        self.assertEqual(response.status_code, 200)
        jogos = list(response.context['jogos'])
        self.assertEqual(len(jogos), 1)
        self.assertEqual(jogos[0].user, self.usuario)


class ExcluirJogoViewTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(email='del@example.com', password='SenhaForte123')
        self.outro_usuario = User.objects.create_user(email='del-outro@example.com', password='SenhaForte123')
        self.client.force_login(self.usuario)

    def test_nao_exclui_jogo_de_outro_usuario(self):
        jogo_alheio = GeneratedBet.objects.create(
            user=self.outro_usuario, game='Mega-sena', contest='1',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        response = self.client.post(reverse('excluir_jogo', args=[jogo_alheio.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(GeneratedBet.objects.filter(pk=jogo_alheio.pk).exists())


class GeneratedBetModelTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(email='model@example.com', password='SenhaForte123')

    def test_get_formatted_numbers(self):
        jogo = GeneratedBet.objects.create(
            user=self.usuario, game='Quina', contest='1',
            numbers=[1, 22, 33, 44, 55], clovers=[], sequential_pairs=0,
        )
        self.assertEqual(jogo.get_formatted_numbers(), '01   22   33   44   55')

    def test_get_formatted_clovers_vazio_retorna_none(self):
        jogo = GeneratedBet.objects.create(
            user=self.usuario, game='Quina', contest='1',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        self.assertIsNone(jogo.get_formatted_clovers())

    def test_has_sequence(self):
        jogo = GeneratedBet.objects.create(
            user=self.usuario, game='Quina', contest='1',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=1,
        )
        self.assertTrue(jogo.has_sequence())
