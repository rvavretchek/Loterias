import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.loterias_core.models import GeneratedBet, LotteryResult, GameStatistics, GAMES_CONFIG
from apps.loterias_core.jobs import fetch_daily_results
from apps.loterias_core.utils import (
    calculate_statistics,
    calculate_bet_prize,
    check_user_results,
    fetch_cef_result,
    count_sequential_pairs,
    generate_bet,
    normalize_numbers,
    check_duplicate_bet,
    suggest_next_contest,
)


class NormalizeNumbersTests(TestCase):
    def test_accepts_comma_separated_string(self):
        self.assertEqual(normalize_numbers('1, 2, 3, 4, 5, 6'), [1, 2, 3, 4, 5, 6])

    def test_accepts_semicolon_separated_string(self):
        self.assertEqual(normalize_numbers('1;2;3'), [1, 2, 3])

    def test_accepts_list(self):
        self.assertEqual(normalize_numbers([1, 2, 3, 4]), [1, 2, 3, 4])

    def test_accepts_single_integer(self):
        self.assertEqual(normalize_numbers(7), [7])

    def test_none_returns_empty_list(self):
        self.assertEqual(normalize_numbers(None), [])

    def test_empty_string_returns_empty_list(self):
        self.assertEqual(normalize_numbers(''), [])


class CountSequentialPairsTests(TestCase):
    def test_empty_list_has_no_pairs(self):
        self.assertEqual(count_sequential_pairs([]), 0)

    def test_single_element_list_has_no_pairs(self):
        self.assertEqual(count_sequential_pairs([5]), 0)

    def test_no_consecutive_numbers(self):
        self.assertEqual(count_sequential_pairs([1, 5, 10, 20]), 0)

    def test_one_consecutive_pair(self):
        self.assertEqual(count_sequential_pairs([1, 5, 10, 11]), 1)

    def test_two_non_overlapping_consecutive_pairs(self):
        self.assertEqual(count_sequential_pairs([1, 2, 10, 11]), 2)

    def test_sorts_before_counting(self):
        self.assertEqual(count_sequential_pairs([11, 1, 10, 2]), 2)

    def test_three_consecutive_numbers_counts_one_pair_with_leftover(self):
        # 1,2,3 -> par (1,2) consumido, 3 fica isolado
        self.assertEqual(count_sequential_pairs([1, 2, 3]), 1)


class GenerateBetTests(TestCase):
    def test_invalid_game_returns_none(self):
        nums, clovers = generate_bet('Jogo-Inexistente')
        self.assertIsNone(nums)
        self.assertIsNone(clovers)

    def test_mega_sena_generates_correct_count_and_range(self):
        for _ in range(20):
            nums, clovers = generate_bet('Mega-sena')
            self.assertEqual(len(nums), 6)
            self.assertEqual(len(set(nums)), 6, 'numeros nao podem se repetir')
            self.assertTrue(all(1 <= n <= 60 for n in nums))
            self.assertEqual(clovers, [])

    def test_milionaria_generates_numbers_and_clovers(self):
        for _ in range(20):
            nums, clovers = generate_bet('Milionaria')
            self.assertEqual(len(nums), 6)
            self.assertTrue(all(1 <= n <= 50 for n in nums))
            self.assertEqual(len(clovers), 2)
            self.assertEqual(len(set(clovers)), 2)
            self.assertTrue(all(1 <= t <= 6 for t in clovers))

    def test_lotomania_generates_50_numbers_up_to_100(self):
        nums, clovers = generate_bet('Lotomania')
        self.assertEqual(len(nums), 50)
        self.assertTrue(all(1 <= n <= 100 for n in nums))

    def test_generated_numbers_are_always_sorted(self):
        for _ in range(10):
            nums, _ = generate_bet('Quina')
            self.assertEqual(nums, sorted(nums))

    def test_blocks_sequential_pair_after_recent_history_with_pair(self):
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

    def test_nonexistent_bet_is_not_duplicate(self):
        self.assertFalse(
            check_duplicate_bet(self.user, 'Mega-sena', [1, 2, 3, 4, 5, 6], [])
        )

    def test_identical_bet_is_duplicate(self):
        GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='100',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=2,
        )
        self.assertTrue(
            check_duplicate_bet(self.user, 'Mega-sena', [1, 2, 3, 4, 5, 6], [])
        )


class SuggestNextContestTests(TestCase):
    def test_no_lottery_result_returns_none(self):
        self.assertIsNone(suggest_next_contest('Mega-sena'))

    def test_returns_max_numeric_contest_plus_one(self):
        LotteryResult.objects.create(game='Mega-sena', contest='2500', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        LotteryResult.objects.create(game='Mega-sena', contest='2498', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        self.assertEqual(suggest_next_contest('Mega-sena'), '2501')

    def test_ignores_non_numeric_special_contest(self):
        LotteryResult.objects.create(game='Mega-sena', contest='2500', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        LotteryResult.objects.create(game='Mega-sena', contest='ESPECIAL-2026', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        self.assertEqual(suggest_next_contest('Mega-sena'), '2501')

    def test_does_not_mix_contests_from_other_games(self):
        LotteryResult.objects.create(game='Quina', contest='9000', numbers=[1, 2, 3, 4, 5], clovers=[], prizes={})
        self.assertIsNone(suggest_next_contest('Mega-sena'))


class CalculateStatisticsTests(TestCase):
    def test_no_bets_returns_none(self):
        user = User.objects.create_user(email='stats1@example.com', password='SenhaForte123')
        self.assertIsNone(calculate_statistics(user, 'Mega-sena'))

    def test_calculates_totals_and_frequency(self):
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
    def test_no_official_result_does_not_win(self):
        prize = calculate_bet_prize('Mega-sena', [1, 2, 3, 4, 5, 6], [], None)
        self.assertFalse(prize['won'])
        self.assertEqual(prize['hits'], 0)
        self.assertEqual(prize['category'], 'Sem resultado')

    def test_mega_sena_with_six_hits_wins(self):
        result = {
            'numbers': [1, 2, 3, 4, 5, 6],
            'clovers': [],
            'prizes': {'6': {'value': 'R$ 500.000,00', 'winners': 1}},
        }
        prize = calculate_bet_prize('Mega-sena', [1, 2, 3, 4, 5, 6], [], result)
        self.assertTrue(prize['won'])
        self.assertEqual(prize['hits'], 6)
        self.assertIn('R$', prize['value'])

    def test_mega_sena_with_three_hits_does_not_win(self):
        result = {
            'numbers': [1, 2, 3, 40, 50, 60],
            'clovers': [],
            'prizes': {'6': {'value': 'R$ 500.000,00', 'winners': 1}},
        }
        prize = calculate_bet_prize('Mega-sena', [1, 2, 3, 4, 5, 6], [], result)
        self.assertFalse(prize['won'])
        self.assertEqual(prize['hits'], 3)
        self.assertEqual(prize['category'], 'Sem premio')

    def test_missing_prize_tier_does_not_raise_error(self):
        result = {'numbers': [1, 2, 3, 4, 5, 6], 'clovers': [], 'prizes': {}}
        prize = calculate_bet_prize('Mega-sena', [1, 2, 3, 4, 5, 6], [], result)
        self.assertFalse(prize['won'])
        self.assertEqual(prize['value'], 'R$ 0,00')

    def test_mega_sena_with_four_hits_uses_quadra_tier_not_sena_tier(self):
        """Regressao: quadra/quina/sena tem faixas de valor bem diferentes -- usar a faixa errada
        (sempre a de 6 acertos) mostraria um valor de premio incorreto pra quem bateu so 4 ou 5."""
        result = {
            'numbers': [1, 2, 3, 4, 50, 60],
            'clovers': [],
            'prizes': {
                '6': {'value': 'R$ 50.000.000,00', 'winners': 0},
                '5': {'value': 'R$ 40.000,00', 'winners': 10},
                '4': {'value': 'R$ 900,00', 'winners': 5000},
            },
        }
        prize = calculate_bet_prize('Mega-sena', [1, 2, 3, 4, 5, 6], [], result)
        self.assertEqual(prize['hits'], 4)
        self.assertTrue(prize['won'])
        self.assertEqual(prize['value'], 'R$ 900,00')


class FetchCefResultTests(TestCase):
    """fetch_cef_result chama a API oficial da CEF (servicebus2.caixa.gov.br) -- sempre mockar requests.get."""

    def _mock_response(self, mock_get, payload, status_ok=True):
        mock_response = Mock()
        mock_response.json.return_value = payload
        mock_response.raise_for_status = Mock() if status_ok else Mock(side_effect=Exception('http error'))
        mock_get.return_value = mock_response
        return mock_response

    def test_unknown_game_returns_none(self):
        self.assertIsNone(fetch_cef_result('Jogo-Inexistente', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_network_error_returns_none_without_raising(self, mock_get):
        mock_get.side_effect = Exception('timeout')
        self.assertIsNone(fetch_cef_result('Mega-sena', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_malformed_json_returns_none_without_raising(self, mock_get):
        mock_response = Mock()
        mock_response.json.side_effect = ValueError('not json')
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        self.assertIsNone(fetch_cef_result('Mega-sena', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_contest_mismatch_returns_none(self, mock_get):
        """Regressao do bug de concurso: a API sempre responde com o concurso pedido na URL,
        mas se por algum motivo o campo 'numero' devolvido nao bater, o resultado e descartado --
        nunca grava dado de um concurso errado sob o nome de outro."""
        self._mock_response(mock_get, {
            'numero': 2501, 'listaDezenas': ['4', '8', '15', '16', '23', '42'], 'listaRateioPremio': [],
        })
        self.assertIsNone(fetch_cef_result('Mega-sena', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_missing_numbers_returns_none(self, mock_get):
        self._mock_response(mock_get, {'numero': 2500, 'listaDezenas': [], 'listaRateioPremio': []})
        self.assertIsNone(fetch_cef_result('Mega-sena', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_matching_contest_returns_result_with_numbers(self, mock_get):
        self._mock_response(mock_get, {
            'numero': 2500,
            'listaDezenas': ['04', '08', '15', '16', '23', '42'],
            'listaRateioPremio': [
                {'descricaoFaixa': '6 acertos', 'faixa': 1, 'numeroDeGanhadores': 0, 'valorPremio': 0.0},
                {'descricaoFaixa': '5 acertos', 'faixa': 2, 'numeroDeGanhadores': 10, 'valorPremio': 5000.0},
            ],
        })
        result = fetch_cef_result('Mega-sena', '2500')
        self.assertIsNotNone(result)
        self.assertEqual(result['game'], 'Mega-sena')
        self.assertEqual(result['contest'], '2500')
        self.assertEqual(result['numbers'], [4, 8, 15, 16, 23, 42])
        self.assertEqual(result['prizes']['6']['value'], 'R$ 0,00')
        self.assertEqual(result['prizes']['5']['value'], 'R$ 5.000,00')
        self.assertEqual(result['prizes']['5']['winners'], 10)

    @patch('apps.loterias_core.utils.requests.get')
    def test_calls_official_api_with_correct_slug_and_contest(self, mock_get):
        """Regressao dos slugs sem hifen (megasena/maismilionaria/duplasena) -- a URL errada
        faria a API oficial devolver 400, e nenhum teste anterior checava a URL de fato usada."""
        self._mock_response(mock_get, {'numero': 2500, 'listaDezenas': ['1'], 'listaRateioPremio': []})
        fetch_cef_result('Mega-sena', '2500')
        mock_get.assert_called_once_with(
            'https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena/2500', timeout=20
        )

    @patch('apps.loterias_core.utils.requests.get')
    def test_http_error_status_returns_none(self, mock_get):
        self._mock_response(mock_get, {'numero': 2500, 'listaDezenas': ['1']}, status_ok=False)
        self.assertIsNone(fetch_cef_result('Mega-sena', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_error_body_without_numero_field_returns_none(self, mock_get):
        """A API oficial responde 400 com um corpo tipo {'Message': ...} quando o concurso nao existe
        (ex. numero futuro demais) -- isso e um dict valido, so sem o campo 'numero'."""
        self._mock_response(mock_get, {'Message': 'The request is invalid.'})
        self.assertIsNone(fetch_cef_result('Mega-sena', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_non_dict_json_body_returns_none(self, mock_get):
        self._mock_response(mock_get, ['nao', 'e', 'um', 'dict'])
        self.assertIsNone(fetch_cef_result('Mega-sena', '2500'))

    @patch('apps.loterias_core.utils.requests.get')
    def test_dupla_sena_duplicate_tier_uses_first_occurrence(self, mock_get):
        """A Dupla-Sena tem 2 sorteios, e listaRateioPremio repete a mesma descricaoFaixa uma vez por
        sorteio (achado confirmado ao vivo contra a API) -- fica com a primeira ocorrencia (1o sorteio)."""
        self._mock_response(mock_get, {
            'numero': 2600,
            'listaDezenas': ['01', '05', '18', '22', '28', '30'],
            'listaRateioPremio': [
                {'descricaoFaixa': '6 acertos', 'faixa': 1, 'numeroDeGanhadores': 0, 'valorPremio': 0.0},
                {'descricaoFaixa': '5 acertos', 'faixa': 2, 'numeroDeGanhadores': 9, 'valorPremio': 5944.77},
                {'descricaoFaixa': '6 acertos', 'faixa': 5, 'numeroDeGanhadores': 1, 'valorPremio': 999999.0},
            ],
        })
        result = fetch_cef_result('Dupla-Sena', '2600')
        self.assertEqual(result['prizes']['6']['winners'], 0)
        self.assertEqual(result['prizes']['6']['value'], 'R$ 0,00')

    @patch('apps.loterias_core.utils.requests.get')
    def test_lotomania_zero_hits_tier_is_extracted(self, mock_get):
        self._mock_response(mock_get, {
            'numero': 2600,
            'listaDezenas': [str(n) for n in range(1, 21)],
            'listaRateioPremio': [
                {'descricaoFaixa': '20 acertos', 'faixa': 1, 'numeroDeGanhadores': 0, 'valorPremio': 0.0},
                {'descricaoFaixa': '0 acertos', 'faixa': 7, 'numeroDeGanhadores': 3, 'valorPremio': 500.0},
            ],
        })
        result = fetch_cef_result('Lotomania', '2600')
        self.assertEqual(result['prizes']['0']['winners'], 3)

    @patch('apps.loterias_core.utils.requests.get')
    def test_milionaria_includes_clovers(self, mock_get):
        self._mock_response(mock_get, {
            'numero': 50,
            'listaDezenas': ['12', '21', '24', '26', '35', '49'],
            'trevosSorteados': ['1', '6'],
            'listaRateioPremio': [],
        })
        result = fetch_cef_result('Milionaria', '50')
        self.assertEqual(result['clovers'], [1, 6])


class CreateBetViewTests(TestCase):
    """Regressao direta do bug documentado em docs/diagnostico-projeto.md:
    gerar um jogo salvo no banco parava de funcionar com a multitenancy."""

    def setUp(self):
        self.user = User.objects.create_user(email='view@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    def test_generating_bet_creates_database_record(self):
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '2500'})
        self.assertEqual(GeneratedBet.objects.filter(user=self.user).count(), 1)
        bet = GeneratedBet.objects.get(user=self.user)
        self.assertEqual(len(bet.numbers), GAMES_CONFIG['Mega-sena']['bets_count'])
        self.assertRedirects(response, reverse('bet_detail', args=[bet.pk]))

    def test_generating_bet_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '2500'})
        self.assertNotEqual(response.status_code, 200)
        self.assertEqual(GeneratedBet.objects.count(), 0)

    def test_generating_bet_without_contest_does_not_create_record(self):
        self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': ''})
        self.assertEqual(GeneratedBet.objects.count(), 0)

    def test_generating_invalid_game_does_not_create_record(self):
        self.client.post(reverse('create_bet'), {'jogo': 'Nao-Existe', 'concurso': '2500'})
        self.assertEqual(GeneratedBet.objects.count(), 0)

    def test_blocks_contest_that_already_has_lottery_result(self):
        LotteryResult.objects.create(game='Mega-sena', contest='2500', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '2500'}, follow=True)
        self.assertEqual(GeneratedBet.objects.count(), 0)
        self.assertRedirects(response, reverse('home'))
        mensagens = [(m.message, m.level_tag) for m in response.context['messages']]
        self.assertIn(('O concurso 2500 de Mega-sena ja foi sorteado. Escolha outro concurso.', 'error'), mensagens)

    def test_blocks_even_when_user_also_has_duplicate_bet(self):
        """As duas checagens coexistem: mesmo com um GeneratedBet duplicado do proprio usuario,
        o bloqueio de concurso ja sorteado vence e nenhum segundo registro e criado."""
        LotteryResult.objects.create(game='Mega-sena', contest='2500', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='2500',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '2500'}, follow=True)
        self.assertEqual(GeneratedBet.objects.filter(user=self.user).count(), 1)
        mensagens = [m.level_tag for m in response.context['messages']]
        self.assertEqual(mensagens, ['error'])

    def test_allows_special_contest_without_lottery_result(self):
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': 'ESPECIAL-2026'})
        self.assertEqual(GeneratedBet.objects.filter(user=self.user).count(), 1)

    def test_api_create_bet_is_not_blocked_by_already_drawn_contest(self):
        """Fora do escopo desta story: api_create_bet_view continua gerando normalmente mesmo
        pra um concurso que ja tem LotteryResult -- decisao explicita das Fronteiras."""
        LotteryResult.objects.create(game='Quina', contest='2500', numbers=[1, 2, 3, 4, 5], clovers=[], prizes={})
        response = self.client.post(
            reverse('api_create_bet'),
            data=json.dumps({'jogo': 'Quina', 'concurso': '2500'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    def test_api_generate_bet_returns_json(self):
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

    def test_history_shows_only_logged_in_users_bets(self):
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

    def test_does_not_delete_another_users_bet(self):
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

    def test_get_formatted_clovers_returns_none_when_empty(self):
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
    def test_manual_bet_creates_record_without_cef_result(self, mock_fetch):
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

    def test_blocks_contest_that_already_has_lottery_result(self):
        LotteryResult.objects.create(game='Lotofacil', contest='3000', numbers=self.numbers, clovers=[], prizes={})
        response = self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Lotofacil',
            'concurso': '3000',
            'numeros': self.numeros_str,
        })
        self.assertEqual(GeneratedBet.objects.count(), 0)
        self.assertRedirects(response, reverse('home'))

    @patch('apps.loterias_core.views.fetch_cef_result')
    def test_allows_special_contest_without_lottery_result(self, mock_fetch):
        mock_fetch.return_value = None
        response = self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Lotofacil',
            'concurso': 'ESPECIAL-2026',
            'numeros': self.numeros_str,
        })
        self.assertEqual(GeneratedBet.objects.filter(user=self.user).count(), 1)

    @patch('apps.loterias_core.views.fetch_cef_result')
    def test_manual_bet_with_cef_result_updates_prize(self, mock_fetch):
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
    def test_result_found_marks_as_checked(self, mock_fetch):
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
    def test_result_not_found_keeps_as_unchecked(self, mock_fetch):
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

    def test_regenerating_bet_creates_new_record_and_redirects(self):
        response = self.client.get(reverse('regenerate_bet', args=[self.bet.pk]))
        bets = GeneratedBet.objects.filter(
            user=self.user, game='Mega-sena', contest='5000'
        )
        self.assertEqual(bets.count(), 2)
        new_bet = bets.exclude(pk=self.bet.pk).get()
        self.assertRedirects(response, reverse('bet_detail', args=[new_bet.pk]))
        self.assertNotEqual(new_bet.pk, self.bet.pk)

    def test_blocks_regenerating_for_contest_that_already_has_lottery_result(self):
        LotteryResult.objects.create(game='Mega-sena', contest='5000', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        response = self.client.get(reverse('regenerate_bet', args=[self.bet.pk]))
        self.assertEqual(GeneratedBet.objects.filter(user=self.user, game='Mega-sena', contest='5000').count(), 1)
        self.assertRedirects(response, reverse('bet_detail', args=[self.bet.pk]))


class StatisticsViewTests(TestCase):
    def test_statistics_contains_game_with_history(self):
        user = User.objects.create_user(email='estat@example.com', password='SenhaForte123')
        self.client.force_login(user)
        GeneratedBet.objects.create(
            user=user, game='Mega-sena', contest='1',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        response = self.client.get(reverse('statistics'))
        self.assertEqual(response.status_code, 200)
        statistics = response.context['estatisticas']
        self.assertTrue(statistics)
        self.assertIn('Mega-sena', statistics)


class HomeViewTests(TestCase):
    def test_authenticated_home_shows_total_bets(self):
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

    def test_home_context_exposes_suggested_contests_rendered_in_html(self):
        user = User.objects.create_user(email='sugestao@example.com', password='SenhaForte123')
        LotteryResult.objects.create(game='Mega-sena', contest='2500', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['concursos_sugeridos']['Mega-sena'], '2501')
        self.assertContains(response, 'id="concursos-sugeridos-data"')
        self.assertContains(response, '"Mega-sena": "2501"')


class BetDetailViewTests(TestCase):
    def test_bet_detail_shows_official_result(self):
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
    def test_result_found_marks_bet_as_checked(self, mock_fetch):
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
    def test_no_result_keeps_bet_unchecked(self, mock_fetch):
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

    def test_generatedbet_admin_list_loads(self):
        response = self.client.get('/admin/loterias_core/generatedbet/')
        self.assertEqual(response.status_code, 200)

    def test_gamestatistics_admin_list_loads(self):
        response = self.client.get('/admin/loterias_core/gamestatistics/')
        self.assertEqual(response.status_code, 200)


class ReverseAccessorTests(TestCase):
    """Cobre user.bets e user.statistics (related_name renomeados na Story 1.1), sem teste ate aqui."""

    def setUp(self):
        self.user = User.objects.create_user(email='reverse@example.com', password='SenhaForte123')

    def test_user_bets_returns_users_bets(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='1',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        self.assertEqual(list(self.user.bets.all()), [bet])

    def test_user_bets_excludes_another_users_bet(self):
        other_user = User.objects.create_user(email='outro@example.com', password='SenhaForte123')
        GeneratedBet.objects.create(
            user=other_user, game='Quina', contest='1',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        self.assertEqual(self.user.bets.count(), 0)

    def test_user_statistics_returns_users_statistics(self):
        stats = GameStatistics.objects.create(
            user=self.user, game='Quina', total_bets=3,
            total_with_sequence=1, total_without_sequence=2,
        )
        self.assertEqual(list(self.user.statistics.all()), [stats])

    def test_user_statistics_excludes_another_users_statistic(self):
        other_user = User.objects.create_user(email='outro2@example.com', password='SenhaForte123')
        GameStatistics.objects.create(user=other_user, game='Quina', total_bets=1)
        self.assertEqual(self.user.statistics.count(), 0)


class FetchDailyResultsJobTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='cron@example.com', password='SenhaForte123')

    def test_pair_without_any_bet_is_not_touched(self):
        fetch_daily_results()
        self.assertEqual(LotteryResult.objects.count(), 0)

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_open_pair_with_valid_result_creates_lottery_result(self, mock_fetch):
        GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='100',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        mock_fetch.return_value = {
            'numbers': [1, 2, 3, 4, 5], 'clovers': [9], 'prizes': {'5': {'value': 'R$ 1.000,00'}},
        }
        fetch_daily_results()
        result = LotteryResult.objects.get(game='Quina', contest='100')
        self.assertEqual(result.numbers, [1, 2, 3, 4, 5])
        self.assertEqual(result.clovers, [9])
        self.assertEqual(result.prizes, {'5': {'value': 'R$ 1.000,00'}})
        self.assertEqual(result.source, 'CEF')

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_two_bets_same_pair_only_fetch_once_per_run(self, mock_fetch):
        GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='105',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        other_user = User.objects.create_user(email='cron2@example.com', password='SenhaForte123')
        GeneratedBet.objects.create(
            user=other_user, game='Quina', contest='105',
            numbers=[6, 7, 8, 9, 10], clovers=[], sequential_pairs=0,
        )
        mock_fetch.return_value = {'numbers': [1, 2, 3, 4, 5], 'clovers': [], 'prizes': {}}
        fetch_daily_results()
        self.assertEqual(mock_fetch.call_count, 1)
        self.assertEqual(LotteryResult.objects.filter(game='Quina', contest='105').count(), 1)

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_rerun_for_same_pair_does_not_duplicate(self, mock_fetch):
        GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='101',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        mock_fetch.return_value = {
            'numbers': [1, 2, 3, 4, 5], 'clovers': [], 'prizes': {},
        }
        fetch_daily_results()
        fetch_daily_results()
        self.assertEqual(LotteryResult.objects.filter(game='Quina', contest='101').count(), 1)

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_failure_in_one_pair_does_not_block_another(self, mock_fetch):
        GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='200',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        GeneratedBet.objects.create(
            user=self.user, game='Lotofacil', contest='300',
            numbers=list(range(1, 16)), clovers=[], sequential_pairs=0,
        )

        def side_effect(game, contest):
            if game == 'Quina':
                raise Exception('falha simulada de scraping')
            return {'numbers': [1, 2, 3], 'clovers': [], 'prizes': {}}

        mock_fetch.side_effect = side_effect
        fetch_daily_results()
        self.assertEqual(LotteryResult.objects.filter(game='Quina', contest='200').count(), 0)
        self.assertEqual(LotteryResult.objects.filter(game='Lotofacil', contest='300').count(), 1)

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_none_result_does_not_create_or_raise(self, mock_fetch):
        GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='400',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        mock_fetch.return_value = None
        fetch_daily_results()
        self.assertEqual(LotteryResult.objects.filter(game='Quina', contest='400').count(), 0)


class FetchDailyResultsCommandTests(TestCase):
    """Cobre a integracao command -> jobs.fetch_daily_results (nao coberta pelos testes que chamam
    a funcao Python diretamente): repasse do --final e descoberta do command pelo Django."""

    @patch('apps.loterias_core.management.commands.fetch_daily_results.fetch_daily_results')
    def test_default_call_passes_final_false(self, mock_job):
        call_command('fetch_daily_results')
        mock_job.assert_called_once_with(final=False)

    @patch('apps.loterias_core.management.commands.fetch_daily_results.fetch_daily_results')
    def test_final_flag_passes_final_true(self, mock_job):
        call_command('fetch_daily_results', '--final')
        mock_job.assert_called_once_with(final=True)
