import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.loterias_core.models import GeneratedBet, LotteryResult, GameStatistics, GAMES_CONFIG
from apps.loterias_core.utils import (
    calculate_statistics,
    calculate_bet_prize,
    check_user_results,
    fetch_cef_result,
    count_sequential_pairs,
    generate_bet,
    normalize_numbers,
    check_duplicate_bet,
)


class NormalizeNumbersTests(TestCase):
    def test_aceita_string_separada_por_virgula(self):
        self.assertEqual(normalize_numbers('1, 2, 3, 4, 5, 6'), [1, 2, 3, 4, 5, 6])

    def test_aceita_string_separada_por_ponto_e_virgula(self):
        self.assertEqual(normalize_numbers('1;2;3'), [1, 2, 3])

    def test_aceita_lista(self):
        self.assertEqual(normalize_numbers([1, 2, 3, 4]), [1, 2, 3, 4])

    def test_aceita_inteiro_unico(self):
        self.assertEqual(normalize_numbers(7), [7])

    def test_none_retorna_lista_vazia(self):
        self.assertEqual(normalize_numbers(None), [])

    def test_string_vazia_retorna_lista_vazia(self):
        self.assertEqual(normalize_numbers(''), [])


class CountSequentialPairsTests(TestCase):
    def test_lista_vazia_sem_pares(self):
        self.assertEqual(count_sequential_pairs([]), 0)

    def test_lista_com_um_elemento_sem_pares(self):
        self.assertEqual(count_sequential_pairs([5]), 0)

    def test_sem_numeros_consecutivos(self):
        self.assertEqual(count_sequential_pairs([1, 5, 10, 20]), 0)

    def test_um_par_consecutivo(self):
        self.assertEqual(count_sequential_pairs([1, 5, 10, 11]), 1)

    def test_dois_pares_consecutivos_nao_sobrepostos(self):
        self.assertEqual(count_sequential_pairs([1, 2, 10, 11]), 2)

    def test_ordena_antes_de_contar(self):
        self.assertEqual(count_sequential_pairs([11, 1, 10, 2]), 2)

    def test_tres_consecutivos_conta_um_par_e_sobra_um(self):
        # 1,2,3 -> par (1,2) consumido, 3 fica isolado
        self.assertEqual(count_sequential_pairs([1, 2, 3]), 1)


class GenerateBetTests(TestCase):
    def test_jogo_invalido_retorna_none(self):
        nums, clovers = generate_bet('Jogo-Inexistente')
        self.assertIsNone(nums)
        self.assertIsNone(clovers)

    def test_mega_sena_gera_quantidade_e_intervalo_corretos(self):
        for _ in range(20):
            nums, clovers = generate_bet('Mega-sena')
            self.assertEqual(len(nums), 6)
            self.assertEqual(len(set(nums)), 6, 'numeros nao podem se repetir')
            self.assertTrue(all(1 <= n <= 60 for n in nums))
            self.assertEqual(clovers, [])

    def test_milionaria_gera_numeros_e_trevos(self):
        for _ in range(20):
            nums, clovers = generate_bet('Milionaria')
            self.assertEqual(len(nums), 6)
            self.assertTrue(all(1 <= n <= 50 for n in nums))
            self.assertEqual(len(clovers), 2)
            self.assertEqual(len(set(clovers)), 2)
            self.assertTrue(all(1 <= t <= 6 for t in clovers))

    def test_lotomania_gera_50_numeros_ate_100(self):
        nums, clovers = generate_bet('Lotomania')
        self.assertEqual(len(nums), 50)
        self.assertTrue(all(1 <= n <= 100 for n in nums))

    def test_numeros_gerados_sempre_ordenados(self):
        for _ in range(10):
            nums, _ = generate_bet('Quina')
            self.assertEqual(nums, sorted(nums))

    def test_bloqueia_sequencia_apos_historico_recente_com_par(self):
        user = User.objects.create_user(email='seq@example.com', password='SenhaForte123')
        GeneratedBet.objects.create(
            user=user, game='Mega-sena', contest='1',
            numbers=[1, 2, 10, 20, 30, 40], clovers=[], sequential_pairs=1,
        )
        for _ in range(30):
            nums, _ = generate_bet('Mega-sena', user)
            self.assertEqual(count_sequential_pairs(nums), 0)


class CheckDuplicateBetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='rep@example.com', password='SenhaForte123')

    def test_jogo_nao_existente_nao_e_repetido(self):
        self.assertFalse(
            check_duplicate_bet(self.user, 'Mega-sena', [1, 2, 3, 4, 5, 6], [])
        )

    def test_jogo_identico_e_repetido(self):
        GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='100',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=2,
        )
        self.assertTrue(
            check_duplicate_bet(self.user, 'Mega-sena', [1, 2, 3, 4, 5, 6], [])
        )


class CalculateStatisticsTests(TestCase):
    def test_sem_jogos_retorna_none(self):
        user = User.objects.create_user(email='stats1@example.com', password='SenhaForte123')
        self.assertIsNone(calculate_statistics(user, 'Mega-sena'))

    def test_calcula_totais_e_frequencia(self):
        user = User.objects.create_user(email='stats2@example.com', password='SenhaForte123')
        GeneratedBet.objects.create(
            user=user, game='Mega-sena', contest='1',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=1,
        )
        GeneratedBet.objects.create(
            user=user, game='Mega-sena', contest='2',
            numbers=[1, 2, 7, 8, 9, 10], clovers=[], sequential_pairs=0,
        )
        stats = calculate_statistics(user, 'Mega-sena')
        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['with_sequence'], 1)
        self.assertEqual(stats['without_sequence'], 1)
        frequency = dict(stats['most_frequent'])
        self.assertEqual(frequency[1], 2)
        self.assertEqual(frequency[2], 2)


class CalculateBetPrizeTests(TestCase):
    def test_sem_resultado_oficial_nao_ganha(self):
        prize = calculate_bet_prize('Mega-sena', [1, 2, 3, 4, 5, 6], [], None)
        self.assertFalse(prize['won'])
        self.assertEqual(prize['hits'], 0)
        self.assertEqual(prize['category'], 'Sem resultado')

    def test_mega_sena_com_seis_acertos_ganha(self):
        result = {
            'numbers': [1, 2, 3, 4, 5, 6],
            'clovers': [],
            'prizes': {'sena': {'value': 'R$ 500.000,00'}},
        }
        prize = calculate_bet_prize('Mega-sena', [1, 2, 3, 4, 5, 6], [], result)
        self.assertTrue(prize['won'])
        self.assertEqual(prize['hits'], 6)
        self.assertIn('R$', prize['value'])

    def test_mega_sena_com_tres_acertos_nao_ganha(self):
        result = {
            'numbers': [1, 2, 3, 40, 50, 60],
            'clovers': [],
            'prizes': {'sena': {'value': 'R$ 500.000,00'}},
        }
        prize = calculate_bet_prize('Mega-sena', [1, 2, 3, 4, 5, 6], [], result)
        self.assertFalse(prize['won'])
        self.assertEqual(prize['hits'], 3)
        self.assertEqual(prize['category'], 'Sem premio')

    def test_premiacao_ausente_para_faixa_nao_gera_erro(self):
        result = {'numbers': [1, 2, 3, 4, 5, 6], 'clovers': [], 'prizes': {}}
        prize = calculate_bet_prize('Mega-sena', [1, 2, 3, 4, 5, 6], [], result)
        self.assertFalse(prize['won'])
        self.assertEqual(prize['value'], 'R$ 0,00')


class FetchCefResultTests(TestCase):
    """fetch_cef_result faz scraping externo -- sempre mockar requests.get."""

    def test_jogo_desconhecido_retorna_none(self):
        self.assertIsNone(fetch_cef_result('Jogo-Inexistente', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_erro_de_rede_retorna_none_sem_levantar_excecao(self, mock_get):
        mock_get.side_effect = Exception('timeout')
        self.assertIsNone(fetch_cef_result('Mega-sena', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_pagina_sem_numeros_reconheciveis_retorna_none(self, mock_get):
        mock_response = Mock()
        mock_response.text = '<html><body>Sem concurso hoje</body></html>'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        self.assertIsNone(fetch_cef_result('Mega-sena', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_pagina_com_numeros_retorna_resultado(self, mock_get):
        html = 'Concurso ' + ''.join(f'>{n}<' for n in [4, 8, 15, 16, 23, 42])
        mock_response = Mock()
        mock_response.text = html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        result = fetch_cef_result('Mega-sena', '2500')
        self.assertIsNotNone(result)
        self.assertEqual(result['game'], 'Mega-sena')
        self.assertEqual(result['numbers'], [4, 8, 15, 16, 23, 42])


class CreateBetViewTests(TestCase):
    """Regressao direta do bug documentado em docs/diagnostico-projeto.md:
    gerar um jogo salvo no banco parava de funcionar com a multitenancy."""

    def setUp(self):
        self.user = User.objects.create_user(email='view@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    def test_gerar_jogo_cria_registro_no_banco(self):
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '2500'})
        self.assertEqual(GeneratedBet.objects.filter(user=self.user).count(), 1)
        bet = GeneratedBet.objects.get(user=self.user)
        self.assertEqual(len(bet.numbers), GAMES_CONFIG['Mega-sena']['bets_count'])
        self.assertRedirects(response, reverse('bet_detail', args=[bet.pk]))

    def test_gerar_jogo_exige_login(self):
        self.client.logout()
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '2500'})
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(GeneratedBet.objects.count(), 0)

    def test_gerar_jogo_sem_concurso_nao_cria_registro(self):
        self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': ''})
        self.assertEqual(GeneratedBet.objects.count(), 0)

    def test_gerar_jogo_invalido_nao_cria_registro(self):
        self.client.post(reverse('create_bet'), {'jogo': 'Nao-Existe', 'concurso': '2500'})
        self.assertEqual(GeneratedBet.objects.count(), 0)

    def test_api_gerar_jogo_retorna_json(self):
        response = self.client.post(
            reverse('api_create_bet'),
            data=json.dumps({'jogo': 'Quina', 'concurso': '2500'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['numeros']), GAMES_CONFIG['Quina']['bets_count'])
        self.assertIsInstance(payload['trevos'], list)
        self.assertIsInstance(payload['pares_sequenciais'], int)
        self.assertGreaterEqual(payload['pares_sequenciais'], 0)
        self.assertIsInstance(payload['repetido'], bool)


class HistoryViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='hist@example.com', password='SenhaForte123')
        self.other_user = User.objects.create_user(email='outro@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    def test_historico_mostra_apenas_jogos_do_usuario_logado(self):
        GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='1',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        GeneratedBet.objects.create(
            user=self.other_user, game='Mega-sena', contest='1',
            numbers=[10, 20, 30, 40, 50, 60], clovers=[], sequential_pairs=0,
        )
        response = self.client.get(reverse('history'))
        self.assertEqual(response.status_code, 200)
        bets = list(response.context['jogos'])
        self.assertEqual(len(bets), 1)
        self.assertEqual(bets[0].user, self.user)


class DeleteBetViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='del@example.com', password='SenhaForte123')
        self.other_user = User.objects.create_user(email='del-outro@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    def test_nao_exclui_jogo_de_outro_usuario(self):
        other_bet = GeneratedBet.objects.create(
            user=self.other_user, game='Mega-sena', contest='1',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        response = self.client.post(reverse('delete_bet', args=[other_bet.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(GeneratedBet.objects.filter(pk=other_bet.pk).exists())


class GeneratedBetModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='model@example.com', password='SenhaForte123')

    def test_get_formatted_numbers(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='1',
            numbers=[1, 22, 33, 44, 55], clovers=[], sequential_pairs=0,
        )
        self.assertEqual(bet.get_formatted_numbers(), '01   22   33   44   55')

    def test_get_formatted_clovers_vazio_retorna_none(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='1',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        self.assertIsNone(bet.get_formatted_clovers())

    def test_has_sequence(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='1',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=1,
        )
        self.assertTrue(bet.has_sequence())


class SaveManualBetViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='manual@example.com', password='SenhaForte123')
        self.client.force_login(self.user)
        config = GAMES_CONFIG['Lotofacil']
        self.numbers = list(range(1, config['bets_count'] + 1))
        self.numeros_str = ','.join(str(n) for n in self.numbers)

    @patch('apps.loterias_core.views.fetch_cef_result')
    def test_jogo_manual_cria_registro_sem_resultado_cef(self, mock_fetch):
        mock_fetch.return_value = None
        response = self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Lotofacil',
            'concurso': '3000',
            'numeros': self.numeros_str,
        })
        self.assertEqual(GeneratedBet.objects.filter(user=self.user).count(), 1)
        bet = GeneratedBet.objects.get(user=self.user)
        self.assertTrue(bet.manual)
        self.assertEqual(bet.numbers, self.numbers)
        self.assertRedirects(response, reverse('bet_detail', args=[bet.pk]))
        self.assertFalse(bet.result_checked)

    @patch('apps.loterias_core.views.fetch_cef_result')
    def test_jogo_manual_com_resultado_cef_atualiza_premio(self, mock_fetch):
        mock_fetch.return_value = {
            'numbers': self.numbers,
            'clovers': [],
            'prizes': {},
        }
        response = self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Lotofacil',
            'concurso': '3001',
            'numeros': self.numeros_str,
        })
        bet = GeneratedBet.objects.get(user=self.user)
        self.assertRedirects(response, reverse('bet_detail', args=[bet.pk]))
        self.assertTrue(
            LotteryResult.objects.filter(game='Lotofacil', contest='3001').exists()
        )
        bet.refresh_from_db()
        self.assertTrue(bet.result_checked)


class CheckBetResultViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='check@example.com', password='SenhaForte123')
        self.client.force_login(self.user)
        self.bet = GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='4000',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=1,
        )

    @patch('apps.loterias_core.views.fetch_cef_result')
    def test_resultado_encontrado_marca_verificado(self, mock_fetch):
        mock_fetch.return_value = {
            'numbers': [1, 2, 3, 4, 5, 6],
            'clovers': [],
            'prizes': {'sena': {'value': 'R$ 500.000,00'}},
        }
        response = self.client.get(reverse('check_bet_result', args=[self.bet.pk]))
        self.assertRedirects(response, reverse('bet_detail', args=[self.bet.pk]))
        self.bet.refresh_from_db()
        self.assertTrue(self.bet.result_checked)

    @patch('apps.loterias_core.views.fetch_cef_result')
    def test_resultado_nao_encontrado_mantem_nao_verificado(self, mock_fetch):
        mock_fetch.return_value = None
        response = self.client.get(reverse('check_bet_result', args=[self.bet.pk]))
        self.assertRedirects(response, reverse('bet_detail', args=[self.bet.pk]))
        self.bet.refresh_from_db()
        self.assertFalse(self.bet.result_checked)


class RegenerateBetViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='regen@example.com', password='SenhaForte123')
        self.client.force_login(self.user)
        self.bet = GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='5000',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=1,
        )

    def test_refazer_jogo_cria_novo_registro_e_redireciona(self):
        response = self.client.get(reverse('regenerate_bet', args=[self.bet.pk]))
        bets = GeneratedBet.objects.filter(
            user=self.user, game='Mega-sena', contest='5000'
        )
        self.assertEqual(bets.count(), 2)
        new_bet = bets.exclude(pk=self.bet.pk).get()
        self.assertRedirects(response, reverse('bet_detail', args=[new_bet.pk]))
        self.assertNotEqual(new_bet.pk, self.bet.pk)


class StatisticsViewTests(TestCase):
    def test_estatisticas_contem_jogo_com_historico(self):
        user = User.objects.create_user(email='estat@example.com', password='SenhaForte123')
        self.client.force_login(user)
        GeneratedBet.objects.create(
            user=user, game='Mega-sena', contest='1',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        response = self.client.get(reverse('statistics'))
        self.assertEqual(response.status_code, 200)
        estatisticas = response.context['estatisticas']
        self.assertTrue(estatisticas)
        self.assertIn('Mega-sena', estatisticas)


class HomeViewTests(TestCase):
    def test_home_autenticado_mostra_total_de_jogos(self):
        user = User.objects.create_user(email='home@example.com', password='SenhaForte123')
        GeneratedBet.objects.create(
            user=user, game='Mega-sena', contest='1',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        GeneratedBet.objects.create(
            user=user, game='Quina', contest='1',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_jogos'], 2)


class BetDetailViewTests(TestCase):
    def test_detalhes_jogo_com_resultado_oficial(self):
        user = User.objects.create_user(email='detalhe@example.com', password='SenhaForte123')
        self.client.force_login(user)
        bet = GeneratedBet.objects.create(
            user=user, game='Mega-sena', contest='6000',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        official_result = LotteryResult.objects.create(
            game='Mega-sena', contest='6000',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[],
            prizes={'sena': {'value': 'R$ 500.000,00'}},
        )
        response = self.client.get(reverse('bet_detail', args=[bet.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context['premio_info'])
        self.assertEqual(response.context['resultado_oficial'], official_result)


class CheckUserResultsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='cur@example.com', password='SenhaForte123')
        self.bet = GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='7000',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
            result_checked=False,
        )

    @patch('apps.loterias_core.utils.fetch_cef_result')
    def test_resultado_encontrado_marca_jogo_como_verificado(self, mock_fetch):
        mock_fetch.return_value = {
            'numbers': [1, 2, 3, 4, 5, 6],
            'clovers': [],
            'prizes': {'sena': {'value': 'R$ 500.000,00'}},
        }
        check_user_results(user=self.user)
        self.bet.refresh_from_db()
        self.assertTrue(self.bet.result_checked)
        self.assertEqual(self.bet.hits, 6)
        self.assertTrue(self.bet.prize_description)

    @patch('apps.loterias_core.utils.fetch_cef_result')
    def test_sem_resultado_mantem_jogo_nao_verificado(self, mock_fetch):
        mock_fetch.return_value = None
        check_user_results(user=self.user)
        self.bet.refresh_from_db()
        self.assertFalse(self.bet.result_checked)


class AdminSmokeTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com', password='SenhaForte123'
        )
        self.client.force_login(self.admin_user)

    def test_generatedbet_admin_lista(self):
        response = self.client.get('/admin/loterias_core/generatedbet/')
        self.assertEqual(response.status_code, 200)

    def test_gamestatistics_admin_lista(self):
        response = self.client.get('/admin/loterias_core/gamestatistics/')
        self.assertEqual(response.status_code, 200)


class ReverseAccessorTests(TestCase):
    """Cobre user.bets e user.statistics (related_name renomeados na Story 1.1), sem teste ate aqui."""

    def setUp(self):
        self.user = User.objects.create_user(email='reverse@example.com', password='SenhaForte123')

    def test_user_bets_retorna_jogos_do_usuario(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='1',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        self.assertEqual(list(self.user.bets.all()), [bet])

    def test_user_bets_nao_inclui_jogo_de_outro_usuario(self):
        outro_usuario = User.objects.create_user(email='outro@example.com', password='SenhaForte123')
        GeneratedBet.objects.create(
            user=outro_usuario, game='Quina', contest='1',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        self.assertEqual(self.user.bets.count(), 0)

    def test_user_statistics_retorna_estatisticas_do_usuario(self):
        stats = GameStatistics.objects.create(
            user=self.user, game='Quina', total_bets=3,
            total_with_sequence=1, total_without_sequence=2,
        )
        self.assertEqual(list(self.user.statistics.all()), [stats])

    def test_user_statistics_nao_inclui_estatistica_de_outro_usuario(self):
        outro_usuario = User.objects.create_user(email='outro2@example.com', password='SenhaForte123')
        GameStatistics.objects.create(user=outro_usuario, game='Quina', total_bets=1)
        self.assertEqual(self.user.statistics.count(), 0)
