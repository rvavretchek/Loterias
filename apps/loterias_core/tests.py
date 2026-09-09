import json
import re
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import Mock, patch

from django.conf import settings
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.loterias_core.models import (
    GeneratedBet, LotteryResult, GameStatistics, HitNotification, NotificationPreference,
    PrizeTier, CaptureFailureAlert, CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS, GAMES_CONFIG,
)
from apps.loterias_core.emails import send_hit_notification_email
from apps.loterias_core.jobs import (
    _alert_operator_of_stale_capture_failures, fetch_daily_results, update_monthly_prize_values,
)
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
    apply_prize_to_bet,
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

    def test_lotomania_zero_hits_wins_when_prize_tier_has_value(self):
        """Regressao: a Lotomania paga por 0 acertos (regra real do jogo) -- won nao pode
        exigir hits > 0, senao esse premio nunca e reconhecido."""
        result = {
            'numbers': list(range(1, 21)),
            'clovers': [],
            'prizes': {'0': {'value': 'R$ 500,00', 'winners': 3}},
        }
        prize = calculate_bet_prize('Lotomania', list(range(21, 71)), [], result)
        self.assertEqual(prize['hits'], 0)
        self.assertTrue(prize['won'])
        self.assertEqual(prize['value'], 'R$ 500,00')

    def test_mega_sena_zero_hits_never_wins(self):
        """Confirma que remover o `hits > 0` de `won` nao abre uma brecha pros outros jogos:
        prize_key so existe acima do piso de acerto de cada Jogo, entao amount fica 0 pra hits=0."""
        result = {'numbers': [1, 2, 3, 4, 5, 6], 'clovers': [], 'prizes': {'6': {'value': 'R$ 1,00'}}}
        prize = calculate_bet_prize('Mega-sena', [40, 41, 42, 43, 44, 45], [], result)
        self.assertEqual(prize['hits'], 0)
        self.assertFalse(prize['won'])

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
            'prizes': {'15': {'value': 'R$ 1.000.000,00', 'winners': 1}},
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
        self.assertEqual(bet.hits, len(self.numbers))
        self.assertEqual(bet.prize, Decimal('1000000.00'))
        self.assertEqual(bet.prize_description, 'lotofacil')


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
            'prizes': {'6': {'value': 'R$ 500.000,00', 'winners': 1}},
        }
        response = self.client.get(reverse('check_bet_result', args=[self.bet.pk]))
        self.assertRedirects(response, reverse('bet_detail', args=[self.bet.pk]))
        self.bet.refresh_from_db()
        self.assertTrue(self.bet.result_checked)
        self.assertEqual(self.bet.hits, 6)
        self.assertEqual(self.bet.prize, Decimal('500000.00'))
        self.assertEqual(self.bet.prize_description, 'sena')

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
            'prizes': {'6': {'value': 'R$ 500.000,00', 'winners': 1}},
        }
        check_user_results(user=self.user)
        self.bet.refresh_from_db()
        self.assertTrue(self.bet.result_checked)
        self.assertEqual(self.bet.hits, 6)
        self.assertEqual(self.bet.prize, Decimal('500000.00'))
        self.assertEqual(self.bet.prize_description, 'sena')

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

    def test_hitnotification_admin_list_loads(self):
        response = self.client.get('/admin/loterias_core/hitnotification/')
        self.assertEqual(response.status_code, 200)

    def test_notificationpreference_admin_list_loads(self):
        response = self.client.get('/admin/loterias_core/notificationpreference/')
        self.assertEqual(response.status_code, 200)

    def test_notificationpreference_admin_add_form_includes_user_field(self):
        """Regressao: um form customizado sem 'user' no Meta.fields, se atribuido a
        ModelAdmin.form, faria o campo user sumir do admin -- a validacao de 'pelo menos 1
        canal' fica no model.clean() exatamente pra nao precisar de form customizado aqui."""
        response = self.client.get('/admin/loterias_core/notificationpreference/add/')
        self.assertContains(response, 'name="user"')

    def test_notificationpreference_admin_blocks_both_channels_disabled(self):
        target_user = User.objects.create_user(email='prefadmin@example.com', password='SenhaForte123')
        response = self.client.post(
            '/admin/loterias_core/notificationpreference/add/', {'user': target_user.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pelo menos um canal')
        self.assertFalse(NotificationPreference.objects.filter(user=target_user).exists())


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


class HitNotificationGenerationTests(TestCase):
    """Story 2.3: varredura de notificacao de acerto dentro de fetch_daily_results."""

    def setUp(self):
        self.user = User.objects.create_user(email='notif@example.com', password='SenhaForte123')

    def test_lotomania_zero_hits_prize_generates_notification(self):
        """Regra corrigida a pedido do Boss: 0 acertos na Lotomania e um premio real,
        entao TEM que gerar HitNotification mesmo sem nenhuma intersecao de numeros."""
        bet = GeneratedBet.objects.create(
            user=self.user, game='Lotomania', contest='9020',
            numbers=list(range(1, 51)), clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Lotomania', contest='9020', numbers=list(range(51, 71)), clovers=[],
            prizes={'0': {'value': 'R$ 500,00', 'winners': 3}},
        )
        with patch('apps.loterias_core.jobs.fetch_cef_result') as mock_fetch:
            mock_fetch.return_value = None
            fetch_daily_results()
        bet.refresh_from_db()
        self.assertEqual(bet.hits, 0)
        notification = HitNotification.objects.get(bet=bet)
        self.assertTrue(notification.won)

    def test_bet_with_hits_and_existing_result_generates_notification(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='9000',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='9000', numbers=[1, 2, 3, 40, 41], clovers=[],
            prizes={'3': {'value': 'R$ 50,00', 'winners': 10}},
        )
        with patch('apps.loterias_core.jobs.fetch_cef_result') as mock_fetch:
            mock_fetch.return_value = None
            fetch_daily_results()
        bet.refresh_from_db()
        self.assertTrue(bet.result_checked)
        self.assertEqual(bet.hits, 3)
        notification = HitNotification.objects.get(bet=bet)
        self.assertTrue(notification.won)
        self.assertFalse(notification.is_read)

    def test_bet_with_hits_but_below_prize_threshold_generates_unwon_notification(self):
        """O gatilho de notificacao e `hits > 0 or won` -- um acerto parcial sem atingir o piso
        de premio do Jogo (won=False) ainda gera HitNotification, so que marcada como nao premiada."""
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='9010',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='9010', numbers=[1, 2, 60, 61, 62], clovers=[], prizes={},
        )
        with patch('apps.loterias_core.jobs.fetch_cef_result') as mock_fetch:
            mock_fetch.return_value = None
            fetch_daily_results()
        notification = HitNotification.objects.get(bet=bet)
        self.assertFalse(notification.won)

    def test_bet_with_zero_hits_does_not_generate_notification_but_updates_cache(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='9001',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='9001', numbers=[10, 20, 30, 40, 50], clovers=[], prizes={},
        )
        with patch('apps.loterias_core.jobs.fetch_cef_result') as mock_fetch:
            mock_fetch.return_value = None
            fetch_daily_results()
        bet.refresh_from_db()
        self.assertTrue(bet.result_checked)
        self.assertEqual(bet.hits, 0)
        self.assertFalse(HitNotification.objects.filter(bet=bet).exists())

    def test_rerun_does_not_duplicate_notification(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='9002',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='9002', numbers=[1, 2, 3, 40, 41], clovers=[], prizes={},
        )
        with patch('apps.loterias_core.jobs.fetch_cef_result') as mock_fetch:
            mock_fetch.return_value = None
            fetch_daily_results()
            fetch_daily_results()
        self.assertEqual(HitNotification.objects.filter(bet=bet).count(), 1)

    def test_covers_lottery_result_written_by_on_demand_path_before_this_run(self):
        """A varredura considera todo GeneratedBet ainda sem cobertura, nao so o LotteryResult
        que a propria chamada gravou -- simula um LotteryResult ja existente antes da execucao."""
        bet = GeneratedBet.objects.create(
            user=self.user, game='Lotofacil', contest='9003',
            numbers=list(range(1, 16)), clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Lotofacil', contest='9003', numbers=list(range(1, 16)), clovers=[],
            prizes={'15': {'value': 'R$ 1.000.000,00', 'winners': 1}},
        )
        with patch('apps.loterias_core.jobs.fetch_cef_result') as mock_fetch:
            mock_fetch.return_value = None
            fetch_daily_results()
        notification = HitNotification.objects.get(bet=bet)
        self.assertTrue(notification.won)

    def test_bet_without_lottery_result_is_not_processed(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='9004',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        with patch('apps.loterias_core.jobs.fetch_cef_result') as mock_fetch:
            mock_fetch.return_value = None
            fetch_daily_results()
        bet.refresh_from_db()
        self.assertFalse(bet.result_checked)
        self.assertFalse(HitNotification.objects.filter(bet=bet).exists())

    def test_failure_processing_one_bet_does_not_block_another(self):
        bet_ok = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='9005',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        bet_broken = GeneratedBet.objects.create(
            user=self.user, game='Lotofacil', contest='9006',
            numbers=list(range(1, 16)), clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='9005', numbers=[1, 2, 3, 40, 41], clovers=[], prizes={},
        )
        LotteryResult.objects.create(
            game='Lotofacil', contest='9006', numbers=list(range(1, 16)), clovers=[], prizes={},
        )
        original_calculate = calculate_bet_prize

        def side_effect(game, numbers, clovers, official_result):
            if game == 'Lotofacil':
                raise Exception('falha simulada')
            return original_calculate(game, numbers, clovers, official_result)

        with patch('apps.loterias_core.jobs.fetch_cef_result') as mock_fetch, \
                patch('apps.loterias_core.jobs.calculate_bet_prize', side_effect=side_effect):
            mock_fetch.return_value = None
            fetch_daily_results()

        self.assertTrue(HitNotification.objects.filter(bet=bet_ok).exists())
        self.assertFalse(HitNotification.objects.filter(bet=bet_broken).exists())


class HitNotificationEmailTests(TestCase):
    """Story 2.7: envio de e-mail de acerto premiado, disparado dentro de _notify_covered_bets."""

    def setUp(self):
        self.user = User.objects.create_user(email='email@example.com', password='SenhaForte123')
        mail.outbox.clear()  # limpa o e-mail de boas-vindas disparado pela criacao do usuario

    def _bet_with_prize(self, contest, numbers=None, prizes=None):
        numbers = numbers or [1, 2, 3, 4, 5]
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest=contest,
            numbers=numbers, clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest=contest, numbers=numbers, clovers=[],
            prizes=prizes if prizes is not None else {'5': {'value': 'R$ 5.000,00', 'winners': 1}},
        )
        return bet

    def _run_job(self):
        with patch('apps.loterias_core.jobs.fetch_cef_result') as mock_fetch:
            mock_fetch.return_value = None
            fetch_daily_results()

    def test_sends_email_when_won_and_email_enabled(self):
        self._bet_with_prize('40')
        NotificationPreference.objects.create(user=self.user, site_enabled=True, email_enabled=True)
        self._run_job()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('email@example.com', mail.outbox[0].to)

    def test_does_not_send_email_without_any_preference_row(self):
        """Ausencia de NotificationPreference e lida como email_enabled=False (default, AD-3)."""
        self._bet_with_prize('41')
        self._run_job()
        self.assertEqual(len(mail.outbox), 0)

    def test_does_not_send_email_when_email_disabled(self):
        self._bet_with_prize('42')
        NotificationPreference.objects.create(user=self.user, site_enabled=True, email_enabled=False)
        self._run_job()
        self.assertEqual(len(mail.outbox), 0)

    def test_does_not_send_email_for_unwon_hit_even_with_email_enabled(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='43',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='43', numbers=[1, 2, 60, 61, 62], clovers=[], prizes={},
        )
        NotificationPreference.objects.create(user=self.user, site_enabled=True, email_enabled=True)
        self._run_job()
        self.assertTrue(HitNotification.objects.filter(bet=bet, won=False).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_does_not_send_email_for_unwon_hit_with_email_disabled(self):
        GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='43b',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='43b', numbers=[1, 2, 60, 61, 62], clovers=[], prizes={},
        )
        NotificationPreference.objects.create(user=self.user, site_enabled=True, email_enabled=False)
        self._run_job()
        self.assertEqual(len(mail.outbox), 0)

    def test_does_not_send_email_for_unwon_hit_without_any_preference_row(self):
        GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='43c',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='43c', numbers=[1, 2, 60, 61, 62], clovers=[], prizes={},
        )
        self._run_job()
        self.assertEqual(len(mail.outbox), 0)

    def test_rerun_does_not_resend_email(self):
        """A rotina nao reenvia porque o bet ja notificado sai do candidate set
        (`notification__isnull=True`, Story 2.3) antes mesmo de chegar no get_or_create/envio --
        e nao especificamente por causa do `if created:` isolado (esse branch so seria alcancado
        se um bet ja notificado voltasse a ser candidato, o que a varredura por estado nao permite
        hoje). O teste confirma o resultado observavel (nao reenvia) via a API publica do job."""
        self._bet_with_prize('44')
        NotificationPreference.objects.create(user=self.user, site_enabled=True, email_enabled=True)
        self._run_job()
        self._run_job()
        self.assertEqual(len(mail.outbox), 1)

    def test_email_failure_does_not_prevent_notification_creation_or_block_others(self):
        bet_ok = self._bet_with_prize('45')
        bet_also_ok = self._bet_with_prize('46', numbers=[10, 11, 12, 13, 14])
        NotificationPreference.objects.create(user=self.user, site_enabled=True, email_enabled=True)
        with patch('apps.loterias_core.jobs.send_hit_notification_email', side_effect=Exception('smtp fora do ar')):
            self._run_job()
        self.assertTrue(HitNotification.objects.filter(bet=bet_ok, won=True).exists())
        self.assertTrue(HitNotification.objects.filter(bet=bet_also_ok, won=True).exists())

    def test_send_mail_failure_inside_emails_module_does_not_propagate(self):
        """Testa o try/except REAL de emails.py (nao o wrapper de jobs.py) -- chama
        send_hit_notification_email diretamente, mockando o send_mail que ela mesma importa."""
        bet = self._bet_with_prize('45b')
        notification = HitNotification.objects.create(bet=bet, won=True)
        with patch('apps.loterias_core.emails.send_mail', side_effect=Exception('smtp fora do ar')):
            try:
                send_hit_notification_email(notification)
            except Exception:
                self.fail('send_hit_notification_email nao deveria propagar excecao do send_mail')

    def test_message_construction_failure_does_not_propagate(self):
        """A montagem da mensagem (nao so o send_mail) tambem fica dentro do try/except."""
        bet = self._bet_with_prize('45c')
        notification = HitNotification.objects.create(bet=bet, won=True)
        with patch('apps.loterias_core.emails.number_format', side_effect=Exception('formatacao quebrada')):
            try:
                send_hit_notification_email(notification)
            except Exception:
                self.fail('send_hit_notification_email nao deveria propagar excecao de formatacao')
        self.assertEqual(len(mail.outbox), 0)

    def test_does_not_send_when_user_email_is_empty(self):
        bet = self._bet_with_prize('45d')
        self.user.email = ''
        self.user.save(update_fields=['email'])
        notification = HitNotification.objects.create(bet=bet, won=True)
        send_hit_notification_email(notification)
        self.assertEqual(len(mail.outbox), 0)

    def test_email_content_includes_game_contest_hits_category_and_formatted_prize(self):
        self._bet_with_prize('47')
        NotificationPreference.objects.create(user=self.user, site_enabled=True, email_enabled=True)
        self._run_job()
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.from_email, settings.DEFAULT_FROM_EMAIL)
        self.assertIn('Quina', sent.subject)
        self.assertIn('47', sent.subject)
        self.assertIn('Quina', sent.body)
        self.assertIn('concurso 47', sent.body)
        self.assertIn('Acertos: 5', sent.body)
        self.assertIn('Categoria: quina', sent.body)
        self.assertIn('5000,00', sent.body)

    def test_multiple_winners_in_the_same_run_each_get_their_own_email(self):
        other_user = User.objects.create_user(email='outroemail@example.com', password='SenhaForte123')
        mail.outbox.clear()
        self._bet_with_prize('48')
        other_bet = GeneratedBet.objects.create(
            user=other_user, game='Quina', contest='49',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='49', numbers=[1, 2, 3, 4, 5], clovers=[],
            prizes={'5': {'value': 'R$ 1.000,00', 'winners': 1}},
        )
        NotificationPreference.objects.create(user=self.user, site_enabled=True, email_enabled=True)
        NotificationPreference.objects.create(user=other_user, site_enabled=True, email_enabled=True)
        self._run_job()
        self.assertEqual(len(mail.outbox), 2)
        recipients = {tuple(m.to) for m in mail.outbox}
        self.assertEqual(recipients, {('email@example.com',), ('outroemail@example.com',)})


class ApplyPrizeToBetTests(TestCase):
    def test_applies_all_cache_fields(self):
        user = User.objects.create_user(email='apply@example.com', password='SenhaForte123')
        bet = GeneratedBet.objects.create(
            user=user, game='Quina', contest='9100',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        prize = {'won': True, 'hits': 3, 'value': 'R$ 50,00', 'category': '3'}
        apply_prize_to_bet(bet, prize)
        bet.refresh_from_db()
        self.assertTrue(bet.result_checked)
        self.assertEqual(bet.hits, 3)
        self.assertEqual(bet.prize, Decimal('50.00'))
        self.assertEqual(bet.prize_description, '3')


class HitNotificationModelTests(TestCase):
    def test_bet_uniqueness_is_enforced_by_the_database(self):
        """A unicidade de HitNotification.bet nao depende so do get_or_create da aplicacao --
        o proprio OneToOneField/banco rejeita um segundo INSERT pro mesmo bet (AD-4)."""
        user = User.objects.create_user(email='unico@example.com', password='SenhaForte123')
        bet = GeneratedBet.objects.create(
            user=user, game='Quina', contest='9200',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=bet, won=True)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                HitNotification.objects.create(bet=bet, won=False)


class NotificationsContextProcessorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='ctxnotif@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    def _bet(self, contest):
        return GeneratedBet.objects.create(
            user=self.user, game='Quina', contest=contest,
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )

    def test_no_notifications_returns_zero(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['unread_notifications_count'], 0)
        self.assertFalse(response.context['has_unread_won_notification'])

    def test_unread_notification_is_counted(self):
        HitNotification.objects.create(bet=self._bet('1'), won=False)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['unread_notifications_count'], 1)
        self.assertFalse(response.context['has_unread_won_notification'])

    def test_won_notification_sets_flag(self):
        HitNotification.objects.create(bet=self._bet('2'), won=True)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['unread_notifications_count'], 1)
        self.assertTrue(response.context['has_unread_won_notification'])

    def test_read_notification_is_not_counted(self):
        HitNotification.objects.create(bet=self._bet('3'), won=True, is_read=True)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['unread_notifications_count'], 0)
        self.assertFalse(response.context['has_unread_won_notification'])

    def test_another_users_notification_is_not_counted(self):
        other_user = User.objects.create_user(email='outrousuario@example.com', password='SenhaForte123')
        other_bet = GeneratedBet.objects.create(
            user=other_user, game='Quina', contest='4',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=other_bet, won=True)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['unread_notifications_count'], 0)

    def test_site_disabled_preference_zeroes_the_badge(self):
        """A escolha 'nao avisar no site' (Story 2.6) precisa ter efeito de verdade -- sem isso,
        desmarcar a caixa nao muda nada pro usuario, contrariando o proprio proposito da story."""
        NotificationPreference.objects.create(user=self.user, site_enabled=False, email_enabled=True)
        HitNotification.objects.create(bet=self._bet('5'), won=True)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['unread_notifications_count'], 0)
        self.assertFalse(response.context['has_unread_won_notification'])

    def test_site_enabled_preference_still_shows_the_badge(self):
        NotificationPreference.objects.create(user=self.user, site_enabled=True, email_enabled=False)
        HitNotification.objects.create(bet=self._bet('6'), won=True)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['unread_notifications_count'], 1)


class NotificationBadgeTemplateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='badge@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    def test_badge_not_shown_without_unread_notification(self):
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'bi-bell-fill')

    def test_badge_shown_with_unread_notification(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='5',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=bet, won=False)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'bi-bell-fill')
        self.assertContains(response, reverse('notifications'))
        self.assertEqual(response.context['unread_notifications_count'], 1)
        self.assertContains(response, 'bg-secondary')

    def test_badge_uses_success_color_when_won_notification_pending(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='6',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=bet, won=True)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'bg-success')

    def test_badge_appears_on_other_pages_too(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='7',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=bet, won=False)
        response = self.client.get(reverse('history'))
        self.assertContains(response, 'bi-bell-fill')


class NotificationsViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='notiflist@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('notifications'))
        self.assertRedirects(response, f"/accounts/login/?next={reverse('notifications')}")

    def test_lists_only_current_users_unread_notifications(self):
        own_bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='6',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        own_notification = HitNotification.objects.create(bet=own_bet, won=True)

        other_user = User.objects.create_user(email='outronotiflist@example.com', password='SenhaForte123')
        other_bet = GeneratedBet.objects.create(
            user=other_user, game='Quina', contest='7',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=other_bet, won=True)

        read_bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='8',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=read_bet, won=True, is_read=True)

        response = self.client.get(reverse('notifications'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['notificacoes']), [own_notification])

    def test_renders_bet_details_and_ordering_for_multiple_notifications(self):
        older_bet = GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='100',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        older = HitNotification.objects.create(bet=older_bet, won=True)

        newer_bet = GeneratedBet.objects.create(
            user=self.user, game='Lotofacil', contest='200',
            numbers=list(range(1, 16)), clovers=[], sequential_pairs=0,
        )
        newer = HitNotification.objects.create(bet=newer_bet, won=False)

        # created_at e auto_now_add -- forca timestamps distintos pra testar a ordenacao
        # (-created_at) sem depender da resolucao do relogio entre 2 creates seguidos.
        HitNotification.objects.filter(pk=older.pk).update(created_at=timezone.now() - timedelta(days=1))

        response = self.client.get(reverse('notifications'))
        self.assertEqual(list(response.context['notificacoes']), [newer, older])
        self.assertContains(response, 'Mega-sena')
        self.assertContains(response, 'Lotofacil')
        self.assertContains(response, '>100<')
        self.assertContains(response, '>200<')
        self.assertContains(response, 'bi-trophy-fill')
        self.assertContains(response, 'Sem premio')

    def test_empty_state_message_shown_when_no_pending_notifications(self):
        response = self.client.get(reverse('notifications'))
        self.assertContains(response, 'Nenhuma notificacao pendente')

    def test_viewing_the_list_does_not_mark_notifications_as_read(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='9',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        notification = HitNotification.objects.create(bet=bet, won=True)
        self.client.get(reverse('notifications'))
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_matched_numbers_shown_for_each_notification(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='10',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='10', numbers=[1, 2, 60, 61, 62], clovers=[], prizes={},
        )
        HitNotification.objects.create(bet=bet, won=False)
        response = self.client.get(reverse('notifications'))
        self.assertEqual(response.context['notificacoes'][0].matched_numbers, [1, 2])
        self.assertContains(response, 'class="numero-bola"', count=2)
        rendered_numbers = re.findall(
            r'class="numero-bola"[^>]*>\s*(\d{2})\s*<', response.content.decode()
        )
        self.assertEqual(rendered_numbers, ['01', '02'])

    def test_matched_numbers_normalizes_string_numbers_like_calculate_bet_prize_does(self):
        """Regressao: bet.numbers/LotteryResult.numbers ja sao sempre int na pratica, mas a
        comparacao usa normalize_numbers() (mesma funcao que calculate_bet_prize usa pra gerar
        bet.hits) em vez de comparar os JSONFields crus -- garante que os dois nunca divirjam."""
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='12',
            numbers=['1', '2', 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='12', numbers=[1, '2', 60, 61, 62], clovers=[], prizes={},
        )
        HitNotification.objects.create(bet=bet, won=False)
        response = self.client.get(reverse('notifications'))
        self.assertEqual(response.context['notificacoes'][0].matched_numbers, [1, 2])

    def test_two_notifications_sharing_the_same_lottery_result(self):
        bet_a = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='13',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        bet_b = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='13',
            numbers=[1, 60, 61, 62, 63], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='13', numbers=[1, 2, 70, 71, 72], clovers=[], prizes={},
        )
        HitNotification.objects.create(bet=bet_a, won=False)
        HitNotification.objects.create(bet=bet_b, won=False)

        response = self.client.get(reverse('notifications'))
        by_bet = {n.bet.pk: n.matched_numbers for n in response.context['notificacoes']}
        self.assertEqual(by_bet[bet_a.pk], [1, 2])
        self.assertEqual(by_bet[bet_b.pk], [1])

    def test_two_notifications_with_different_lottery_results_on_same_page(self):
        bet_mega = GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='14',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        bet_quina = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='14',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Mega-sena', contest='14', numbers=[1, 2, 40, 41, 42, 43], clovers=[], prizes={},
        )
        LotteryResult.objects.create(
            game='Quina', contest='14', numbers=[1, 50, 51, 52, 53], clovers=[], prizes={},
        )
        HitNotification.objects.create(bet=bet_mega, won=False)
        HitNotification.objects.create(bet=bet_quina, won=False)

        response = self.client.get(reverse('notifications'))
        by_bet = {n.bet.pk: n.matched_numbers for n in response.context['notificacoes']}
        self.assertEqual(by_bet[bet_mega.pk], [1, 2])
        self.assertEqual(by_bet[bet_quina.pk], [1])

    def test_missing_lottery_result_falls_back_to_empty_and_shows_placeholder(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='15',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=bet, won=False)
        response = self.client.get(reverse('notifications'))
        self.assertEqual(response.context['notificacoes'][0].matched_numbers, [])
        self.assertNotContains(response, 'class="numero-bola"')

    def test_prize_value_shown_when_won(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='11',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
            hits=3, prize=Decimal('50.00'), prize_description='quina',
        )
        HitNotification.objects.create(bet=bet, won=True)
        response = self.client.get(reverse('notifications'))
        self.assertContains(response, '50,00')

    def test_mark_as_read_form_is_rendered_for_each_notification(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='16',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        notification = HitNotification.objects.create(bet=bet, won=True)
        response = self.client.get(reverse('notifications'))
        self.assertContains(response, reverse('mark_notification_read', args=[notification.pk]))
        self.assertContains(response, 'bi-check2')


class MarkNotificationReadViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='marcarlida@example.com', password='SenhaForte123')
        self.client.force_login(self.user)
        self.bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='20',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        self.notification = HitNotification.objects.create(bet=self.bet, won=True)

    def test_marks_only_the_clicked_notification_as_read(self):
        other_bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='21',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        other_notification = HitNotification.objects.create(bet=other_bet, won=True)

        response = self.client.post(reverse('mark_notification_read', args=[self.notification.pk]))
        self.assertRedirects(response, reverse('notifications'))

        self.notification.refresh_from_db()
        other_notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)
        self.assertFalse(other_notification.is_read)

    def test_read_notification_disappears_from_badge_and_list(self):
        self.client.post(reverse('mark_notification_read', args=[self.notification.pk]))
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['unread_notifications_count'], 0)
        response = self.client.get(reverse('notifications'))
        self.assertEqual(list(response.context['notificacoes']), [])

    def test_cannot_mark_another_users_notification_as_read(self):
        other_user = User.objects.create_user(email='outromarcar@example.com', password='SenhaForte123')
        other_bet = GeneratedBet.objects.create(
            user=other_user, game='Quina', contest='22',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        other_notification = HitNotification.objects.create(bet=other_bet, won=True)

        self.client.post(reverse('mark_notification_read', args=[other_notification.pk]))

        other_notification.refresh_from_db()
        self.assertFalse(other_notification.is_read)

    def test_nonexistent_pk_does_not_error(self):
        response = self.client.post(reverse('mark_notification_read', args=[999999]))
        self.assertRedirects(response, reverse('notifications'))

    def test_response_does_not_leak_whether_notification_exists(self):
        """Mesmo redirect (302 pra 'notifications') tanto pra um pk que pertence ao usuario
        quanto pra um pk de outro usuario ou inexistente -- nenhuma pista de qual e qual."""
        other_user = User.objects.create_user(email='outroleak@example.com', password='SenhaForte123')
        other_bet = GeneratedBet.objects.create(
            user=other_user, game='Quina', contest='23',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        other_notification = HitNotification.objects.create(bet=other_bet, won=True)

        own_response = self.client.post(reverse('mark_notification_read', args=[self.notification.pk]))
        foreign_response = self.client.post(reverse('mark_notification_read', args=[other_notification.pk]))
        missing_response = self.client.post(reverse('mark_notification_read', args=[999999]))

        self.assertEqual(own_response.status_code, foreign_response.status_code)
        self.assertEqual(own_response.status_code, missing_response.status_code)
        self.assertEqual(own_response.url, foreign_response.url)
        self.assertEqual(own_response.url, missing_response.url)

    def test_redirects_to_next_when_provided_to_preserve_pagination_page(self):
        response = self.client.post(
            reverse('mark_notification_read', args=[self.notification.pk]),
            {'next': reverse('notifications') + '?page=2'},
        )
        self.assertRedirects(response, reverse('notifications') + '?page=2')

    def test_ignores_next_pointing_outside_the_site(self):
        response = self.client.post(
            reverse('mark_notification_read', args=[self.notification.pk]),
            {'next': 'https://evil.example.com/'},
        )
        self.assertRedirects(response, reverse('notifications'))

    def test_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse('mark_notification_read', args=[self.notification.pk]))
        self.assertRedirects(
            response, f"/accounts/login/?next={reverse('mark_notification_read', args=[self.notification.pk])}"
        )

    def test_get_request_does_not_mark_as_read(self):
        response = self.client.get(reverse('mark_notification_read', args=[self.notification.pk]))
        self.assertEqual(response.status_code, 405)
        self.notification.refresh_from_db()
        self.assertFalse(self.notification.is_read)


class NotificationPreferenceModelTests(TestCase):
    def test_user_uniqueness_is_enforced_by_the_database(self):
        user = User.objects.create_user(email='prefunico@example.com', password='SenhaForte123')
        NotificationPreference.objects.create(user=user)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NotificationPreference.objects.create(user=user)

    def test_clean_rejects_both_channels_disabled(self):
        user = User.objects.create_user(email='prefclean@example.com', password='SenhaForte123')
        preference = NotificationPreference(user=user, site_enabled=False, email_enabled=False)
        with self.assertRaises(ValidationError):
            preference.full_clean()

    def test_database_constraint_rejects_both_channels_disabled_even_bypassing_full_clean(self):
        """`Model.save()` nao chama full_clean() sozinho (gotcha conhecido do Django) -- a
        CheckConstraint no banco e o backstop real contra qualquer caminho (admin sem o form
        certo, script, data migration) que grave os 2 canais desativados sem passar por clean()."""
        user = User.objects.create_user(email='prefconstraint@example.com', password='SenhaForte123')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                NotificationPreference.objects.create(user=user, site_enabled=False, email_enabled=False)


class NotificationPreferencesViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='prefview@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('notification_preferences'))
        self.assertRedirects(response, f"/accounts/login/?next={reverse('notification_preferences')}")

    def test_first_access_shows_defaults_without_saving_a_user_change(self):
        response = self.client.get(reverse('notification_preferences'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].initial['site_enabled'])
        self.assertFalse(response.context['form'].initial['email_enabled'])
        self.assertNotContains(response, 'Preferencia de notificacao atualizada')

    def test_get_or_create_on_first_access_materializes_the_default_row(self):
        """A ausencia de linha e lida como os defaults (AD-3) -- o get_or_create de leitura
        grava a linha com os defaults, mas isso nao conta como 'mudanca do usuario'."""
        self.assertFalse(NotificationPreference.objects.filter(user=self.user).exists())
        self.client.get(reverse('notification_preferences'))
        preference = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(preference.site_enabled)
        self.assertFalse(preference.email_enabled)

    def test_saving_only_site_enabled(self):
        response = self.client.post(reverse('notification_preferences'), {'site_enabled': 'on'})
        self.assertRedirects(response, reverse('notification_preferences'))
        preference = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(preference.site_enabled)
        self.assertFalse(preference.email_enabled)

    def test_saving_only_email_enabled(self):
        response = self.client.post(reverse('notification_preferences'), {'email_enabled': 'on'})
        self.assertRedirects(response, reverse('notification_preferences'))
        preference = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(preference.site_enabled)
        self.assertTrue(preference.email_enabled)

    def test_saving_both_enabled(self):
        response = self.client.post(
            reverse('notification_preferences'), {'site_enabled': 'on', 'email_enabled': 'on'}
        )
        self.assertRedirects(response, reverse('notification_preferences'))
        preference = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(preference.site_enabled)
        self.assertTrue(preference.email_enabled)

    def test_disabling_both_channels_is_blocked_and_keeps_previous_preference(self):
        NotificationPreference.objects.create(user=self.user, site_enabled=True, email_enabled=True)
        response = self.client.post(reverse('notification_preferences'), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Pelo menos um canal')
        preference = NotificationPreference.objects.get(user=self.user)
        self.assertTrue(preference.site_enabled)
        self.assertTrue(preference.email_enabled)

    def test_changing_preference_does_not_touch_existing_hit_notifications(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='30',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        notification = HitNotification.objects.create(bet=bet, won=True, is_read=False)
        self.client.post(reverse('notification_preferences'), {'email_enabled': 'on'})
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)
        self.assertTrue(HitNotification.objects.filter(pk=notification.pk).exists())

    def test_anonymous_post_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse('notification_preferences'), {'site_enabled': 'on'})
        self.assertRedirects(response, f"/accounts/login/?next={reverse('notification_preferences')}")
        self.assertFalse(NotificationPreference.objects.filter(user=self.user).exists())

    def test_default_checkboxes_rendered_correctly_in_html(self):
        response = self.client.get(reverse('notification_preferences'))
        html = response.content.decode()
        self.assertContains(response, 'type="checkbox"', count=2)
        site_input = re.search(r'<input[^>]*name="site_enabled"[^>]*>', html).group()
        email_input = re.search(r'<input[^>]*name="email_enabled"[^>]*>', html).group()
        self.assertIn('checked', site_input)
        self.assertNotIn('checked', email_input)

    def test_exact_validation_error_message_rendered(self):
        NotificationPreference.objects.create(user=self.user, site_enabled=True, email_enabled=True)
        response = self.client.post(reverse('notification_preferences'), {})
        self.assertContains(
            response, 'Pelo menos um canal de aviso (site ou e-mail) precisa continuar ativo.'
        )

    def test_success_message_shown_after_saving(self):
        response = self.client.post(
            reverse('notification_preferences'), {'site_enabled': 'on'}, follow=True
        )
        self.assertContains(response, 'Preferencia de notificacao atualizada com sucesso!')

    def test_does_not_read_or_affect_another_users_preference(self):
        other_user = User.objects.create_user(email='outropreferencia@example.com', password='SenhaForte123')
        NotificationPreference.objects.create(user=other_user, site_enabled=False, email_enabled=True)

        self.client.post(reverse('notification_preferences'), {'site_enabled': 'on'})

        own_preference = NotificationPreference.objects.get(user=self.user)
        other_preference = NotificationPreference.objects.get(user=other_user)
        self.assertTrue(own_preference.site_enabled)
        self.assertFalse(other_preference.site_enabled)
        self.assertTrue(other_preference.email_enabled)


class UpdateMonthlyPrizeValuesTests(TestCase):
    def test_captures_one_prize_tier_per_hits_from_latest_lottery_result(self):
        LotteryResult.objects.create(
            game='Quina', contest='500', numbers=[1, 2, 3, 4, 5], clovers=[],
            prizes={
                '5': {'value': 'R$ 100.000,00', 'winners': 2},
                '4': {'value': 'R$ 500,00', 'winners': 50},
            },
        )
        update_monthly_prize_values()
        reference_month = timezone.now().date().replace(day=1)
        tier5 = PrizeTier.objects.get(game='Quina', hits=5, reference_month=reference_month)
        tier4 = PrizeTier.objects.get(game='Quina', hits=4, reference_month=reference_month)
        self.assertEqual(tier5.value, Decimal('100000.00'))
        self.assertEqual(tier5.winners, 2)
        self.assertEqual(tier4.value, Decimal('500.00'))

    def test_zero_value_tier_is_still_captured(self):
        """Um concurso acumulado sem ganhador ainda tem a faixa valida -- nao filtrar por
        valor/ganhadores > 0, senao a faixa 'some' do PrizeTier num mes acumulado."""
        LotteryResult.objects.create(
            game='Mega-sena', contest='600', numbers=[1, 2, 3, 4, 5, 6], clovers=[],
            prizes={'6': {'value': 'R$ 0,00', 'winners': 0}},
        )
        update_monthly_prize_values()
        reference_month = timezone.now().date().replace(day=1)
        tier = PrizeTier.objects.get(game='Mega-sena', hits=6, reference_month=reference_month)
        self.assertEqual(tier.value, Decimal('0.00'))
        self.assertEqual(tier.winners, 0)

    def test_no_lottery_result_for_game_is_skipped_without_error(self):
        update_monthly_prize_values()
        self.assertEqual(PrizeTier.objects.count(), 0)

    def test_failure_capturing_one_game_does_not_block_the_others(self):
        LotteryResult.objects.create(
            game='Quina', contest='800', numbers=[1, 2, 3, 4, 5], clovers=[],
            prizes={'5': {'value': 'R$ 1,00', 'winners': 1}},
        )
        LotteryResult.objects.create(
            game='Lotofacil', contest='801', numbers=list(range(1, 16)), clovers=[],
            prizes={'15': {'value': 'R$ 1,00', 'winners': 1}},
        )

        def side_effect(*args, **kwargs):
            if kwargs.get('game') == 'Lotofacil':
                raise Exception('falha simulada')
            defaults = kwargs['defaults']
            return PrizeTier.objects.create(
                game=kwargs['game'], hits=kwargs['hits'], reference_month=kwargs['reference_month'],
                value=defaults['value'], winners=defaults['winners'],
            ), True

        with patch('apps.loterias_core.jobs.PrizeTier.objects.update_or_create', side_effect=side_effect):
            update_monthly_prize_values()

        self.assertTrue(PrizeTier.objects.filter(game='Quina', hits=5).exists())
        self.assertFalse(PrizeTier.objects.filter(game='Lotofacil').exists())

    def test_retention_keeps_only_the_3_most_recent_reference_months(self):
        """As linhas sao criadas fora de ordem cronologica de insercao de proposito -- se a poda um
        dia passar a ordenar por PK/ordem de criacao em vez de reference_month, este teste tem que
        quebrar (regressao da revisao: a ordem de PK e a ordem de reference_month coincidirem
        mascararia esse bug)."""
        months = [date(2025, 9, 1), date(2026, 1, 1), date(2025, 11, 1), date(2025, 10, 1), date(2025, 12, 1)]
        for month in months:
            PrizeTier.objects.create(game='Quina', hits=5, reference_month=month, value=Decimal('10.00'), winners=1)
        update_monthly_prize_values()
        remaining = set(PrizeTier.objects.filter(game='Quina', hits=5).values_list('reference_month', flat=True))
        self.assertEqual(remaining, {date(2026, 1, 1), date(2025, 12, 1), date(2025, 11, 1)})

    def test_idempotent_rerun_updates_the_value_not_only_avoids_duplicating(self):
        result = LotteryResult.objects.create(
            game='Lotofacil', contest='700', numbers=list(range(1, 16)), clovers=[],
            prizes={'15': {'value': 'R$ 1.000,00', 'winners': 1}},
        )
        update_monthly_prize_values()
        first_tier = PrizeTier.objects.get(game='Lotofacil', hits=15)
        self.assertEqual(first_tier.value, Decimal('1000.00'))

        result.prizes = {'15': {'value': 'R$ 2.500,00', 'winners': 4}}
        result.save(update_fields=['prizes'])
        update_monthly_prize_values()

        self.assertEqual(PrizeTier.objects.filter(game='Lotofacil', hits=15).count(), 1)
        second_tier = PrizeTier.objects.get(game='Lotofacil', hits=15)
        self.assertEqual(second_tier.value, Decimal('2500.00'))
        self.assertEqual(second_tier.winners, 4)

    def test_failure_writing_one_tier_does_not_block_sibling_tiers_of_the_same_game(self):
        """O try/except de gravacao e por faixa, nao por Jogo inteiro -- uma falha isolada na
        faixa de 5 acertos nao pode impedir a faixa de 4 acertos do mesmo concurso de ser
        capturada."""
        LotteryResult.objects.create(
            game='Quina', contest='900', numbers=[1, 2, 3, 4, 5], clovers=[],
            prizes={
                '5': {'value': 'R$ 1,00', 'winners': 1},
                '4': {'value': 'R$ 2,00', 'winners': 2},
            },
        )
        original_update_or_create = PrizeTier.objects.update_or_create

        def side_effect(*args, **kwargs):
            if kwargs.get('hits') == 5:
                raise Exception('falha simulada')
            return original_update_or_create(*args, **kwargs)

        with patch('apps.loterias_core.jobs.PrizeTier.objects.update_or_create', side_effect=side_effect):
            update_monthly_prize_values()

        self.assertFalse(PrizeTier.objects.filter(game='Quina', hits=5).exists())
        self.assertTrue(PrizeTier.objects.filter(game='Quina', hits=4).exists())

    def test_latest_result_picked_by_contest_number_not_by_capture_time(self):
        """Regressao: captured_at reflete quando a linha foi gravada no banco, nao a ordem real
        dos concursos -- uma verificacao manual tardia de um concurso antigo nao pode ser tratada
        como 'o resultado mais recente' do Jogo."""
        LotteryResult.objects.create(
            game='Quina', contest='950', numbers=[1, 2, 3, 4, 5], clovers=[],
            prizes={'5': {'value': 'R$ 999,00', 'winners': 1}},
        )
        old_result = LotteryResult.objects.create(
            game='Quina', contest='800', numbers=[6, 7, 8, 9, 10], clovers=[],
            prizes={'5': {'value': 'R$ 1,00', 'winners': 99}},
        )
        LotteryResult.objects.filter(pk=old_result.pk).update(captured_at=timezone.now())

        update_monthly_prize_values()

        tier = PrizeTier.objects.get(game='Quina', hits=5)
        self.assertEqual(tier.value, Decimal('999.00'))


class CalculateBetPrizeWithPrizeTierTests(TestCase):
    def test_hits_valid_via_prize_tier_even_below_legacy_minimum(self):
        """Regressao: antes da Story 2.8 a Mega-Sena exigia >=4 acertos hardcoded (LEGACY_MIN_HITS).
        Com PrizeTier atestando que existe faixa pra 2 acertos no mes, ela tem que valer mesmo
        abaixo do piso legado -- so o legado se aplica em cold-start total (nenhum PrizeTier pro Jogo)."""
        reference_month = timezone.now().date().replace(day=1)
        PrizeTier.objects.create(
            game='Mega-sena', hits=2, reference_month=reference_month, value=Decimal('50.00'), winners=100
        )
        result = {'numbers': [1, 2, 3, 4, 5, 6], 'clovers': [], 'prizes': {}}
        prize = calculate_bet_prize('Mega-sena', [1, 2, 40, 41, 42, 43], [], result)
        self.assertEqual(prize['hits'], 2)
        self.assertTrue(prize['won'])
        self.assertEqual(prize['value'], 'R$ 50,00')

    def test_prize_tier_exists_for_game_but_hits_uncovered_does_not_fall_back_to_legacy(self):
        """Uma vez que o Jogo ja tem PrizeTier (nao e mais cold-start), uma quantidade de acertos
        sem faixa correspondente fica invalida -- nao pode recair no piso legado, que so existe
        pra cobrir o cold-start total."""
        reference_month = timezone.now().date().replace(day=1)
        PrizeTier.objects.create(
            game='Mega-sena', hits=6, reference_month=reference_month, value=Decimal('1000000.00'), winners=1
        )
        result = {'numbers': [1, 2, 3, 4, 40, 41], 'clovers': [], 'prizes': {}}
        prize = calculate_bet_prize('Mega-sena', [1, 2, 3, 4, 50, 51], [], result)
        self.assertEqual(prize['hits'], 4)
        self.assertFalse(prize['won'])

    def test_reference_month_selects_most_recent_tier_not_exceeding_captured_at(self):
        """3 tiers ficam simultaneamente elegiveis (reference_month <= captured_at) com valores
        diferentes -- precisa escolher o mais proximo (2026-01), nao o mais antigo elegivel
        (2025-11), senao uma ordenacao invertida (ascendente) passaria por engano."""
        PrizeTier.objects.create(
            game='Quina', hits=5, reference_month=date(2025, 11, 1), value=Decimal('50.00'), winners=1
        )
        PrizeTier.objects.create(
            game='Quina', hits=5, reference_month=date(2025, 12, 1), value=Decimal('80.00'), winners=1
        )
        PrizeTier.objects.create(
            game='Quina', hits=5, reference_month=date(2026, 1, 1), value=Decimal('100.00'), winners=1
        )
        PrizeTier.objects.create(
            game='Quina', hits=5, reference_month=date(2026, 3, 1), value=Decimal('200.00'), winners=1
        )
        captured_at = timezone.now().replace(year=2026, month=1, day=15)
        result = {'numbers': [1, 2, 3, 4, 5], 'clovers': [], 'prizes': {}, 'captured_at': captured_at}
        prize = calculate_bet_prize('Quina', [1, 2, 3, 4, 5], [], result)
        self.assertEqual(prize['value'], 'R$ 100,00')

    def test_amount_falls_back_to_prize_tier_value_when_missing_from_concurso_prizes(self):
        reference_month = timezone.now().date().replace(day=1)
        PrizeTier.objects.create(
            game='Quina', hits=5, reference_month=reference_month, value=Decimal('777.00'), winners=1
        )
        result = {'numbers': [1, 2, 3, 4, 5], 'clovers': [], 'prizes': {}}
        prize = calculate_bet_prize('Quina', [1, 2, 3, 4, 5], [], result)
        self.assertTrue(prize['won'])
        self.assertEqual(prize['value'], 'R$ 777,00')

    def test_concurso_specific_prizes_remain_ground_truth_even_after_prize_tier_pruning(self):
        """Regressao critica: uma aposta antiga genuinamente premiada nao pode perder o
        reconhecimento do premio so porque a retencao de 3 meses do PrizeTier (Story 2.8/AD-10)
        ja descartou o reference_month dela -- o LotteryResult do proprio concurso (nunca podado,
        AD-10) e a fonte da verdade e tem prioridade sobre o PrizeTier."""
        PrizeTier.objects.create(
            game='Quina', hits=5, reference_month=date(2026, 6, 1), value=Decimal('1.00'), winners=1
        )
        old_captured_at = timezone.now().replace(year=2025, month=1, day=10)
        result = {
            'numbers': [1, 2, 3, 4, 5], 'clovers': [], 'captured_at': old_captured_at,
            'prizes': {'5': {'value': 'R$ 250.000,00', 'winners': 2}},
        }
        prize = calculate_bet_prize('Quina', [1, 2, 3, 4, 5], [], result)
        self.assertTrue(prize['won'])
        self.assertEqual(prize['value'], 'R$ 250.000,00')

    def test_no_eligible_tier_and_no_concurso_data_does_not_fall_back_to_legacy(self):
        """Quando o Jogo ja tem PrizeTier (nao e cold-start) mas nem o concurso especifico nem
        nenhum PrizeTier elegivel (reference_month <= captured_at) cobrem essa quantidade de
        acertos, o resultado e invalido -- nao pode recair no piso legado (Quina exigiria so 3
        acertos no legado, o que mascararia esse bug)."""
        PrizeTier.objects.create(
            game='Quina', hits=5, reference_month=date(2026, 6, 1), value=Decimal('1.00'), winners=1
        )
        old_captured_at = timezone.now().replace(year=2025, month=1, day=10)
        result = {
            'numbers': [1, 2, 3, 4, 5], 'clovers': [], 'captured_at': old_captured_at, 'prizes': {},
        }
        prize = calculate_bet_prize('Quina', [1, 2, 3, 4, 5], [], result)
        self.assertFalse(prize['won'])

    def test_lotomania_zero_hits_via_prize_tier_path_not_legacy(self):
        """Cobre o Code Map da Story 2.8: hits=0 da Lotomania funcionando pelo caminho novo
        (PrizeTier), nao so pelo fallback legado que ja tratava a Lotomania como sempre valida."""
        reference_month = timezone.now().date().replace(day=1)
        PrizeTier.objects.create(
            game='Lotomania', hits=0, reference_month=reference_month, value=Decimal('500.00'), winners=3
        )
        result = {'numbers': list(range(1, 21)), 'clovers': [], 'prizes': {}}
        prize = calculate_bet_prize('Lotomania', list(range(21, 71)), [], result)
        self.assertEqual(prize['hits'], 0)
        self.assertTrue(prize['won'])
        self.assertEqual(prize['value'], 'R$ 500,00')

    def test_reference_month_uses_local_timezone_not_utc(self):
        """Regressao de fuso: TIME_ZONE e America/Sao_Paulo -- um captured_at logo apos a meia-noite
        UTC ainda pode ser o dia (e mes) anterior em Brasilia, e reference_month tem que refletir o
        mes local, nao o mes UTC."""
        utc_captured_at = datetime(2026, 2, 1, 2, 0, 0, tzinfo=dt_timezone.utc)
        PrizeTier.objects.create(
            game='Quina', hits=5, reference_month=date(2026, 1, 1), value=Decimal('321.00'), winners=1
        )
        result = {
            'numbers': [1, 2, 3, 4, 5], 'clovers': [], 'captured_at': utc_captured_at, 'prizes': {},
        }
        prize = calculate_bet_prize('Quina', [1, 2, 3, 4, 5], [], result)
        self.assertEqual(prize['value'], 'R$ 321,00')


class FetchDailyResultsCallsUpdateMonthlyPrizeValuesTests(TestCase):
    """Cold-start safety (Story 2.8): update_monthly_prize_values roda a cada execucao diaria,
    nao so no cron mensal -- assim o mes corrente nunca fica sem PrizeTier ate o dia 1 rodar."""

    @patch('apps.loterias_core.jobs.update_monthly_prize_values')
    def test_fetch_daily_results_calls_update_monthly_prize_values(self, mock_update):
        fetch_daily_results()
        mock_update.assert_called_once()

    @patch('apps.loterias_core.jobs.update_monthly_prize_values')
    def test_fetch_daily_results_survives_update_monthly_prize_values_failure(self, mock_update):
        mock_update.side_effect = Exception('falha simulada')
        result = fetch_daily_results()
        self.assertTrue(result)

    @patch('apps.loterias_core.jobs.update_monthly_prize_values')
    @patch('apps.loterias_core.jobs._notify_covered_bets')
    def test_update_monthly_prize_values_runs_after_the_notification_sweep(self, mock_notify, mock_update):
        call_order = []
        mock_notify.side_effect = lambda: call_order.append('notify') or 0
        mock_update.side_effect = lambda: call_order.append('update')
        fetch_daily_results()
        self.assertEqual(call_order, ['notify', 'update'])


class UpdateMonthlyPrizeValuesCommandTests(TestCase):
    @patch('apps.loterias_core.management.commands.update_monthly_prize_values.update_monthly_prize_values')
    def test_command_calls_the_job(self, mock_job):
        call_command('update_monthly_prize_values')
        mock_job.assert_called_once_with()


@override_settings(OPERATOR_ALERT_EMAIL='boss@example.com')
class CaptureFailureAlertTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='alertjob@example.com', password='SenhaForte123')
        mail.outbox.clear()

    def _create_stale_bet(self, game='Quina', contest='999', days_old=CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS):
        bet = GeneratedBet.objects.create(
            user=self.user, game=game, contest=contest,
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        GeneratedBet.objects.filter(pk=bet.pk).update(
            created_at=timezone.now() - timedelta(days=days_old)
        )
        return bet

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_non_final_execution_never_alerts_even_for_a_stale_pair(self, mock_fetch):
        self._create_stale_bet()
        mock_fetch.return_value = None
        fetch_daily_results(final=False)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(CaptureFailureAlert.objects.exists())

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_pair_open_for_fewer_than_the_threshold_days_does_not_alert(self, mock_fetch):
        self._create_stale_bet(days_old=CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS - 1)
        mock_fetch.return_value = None
        fetch_daily_results(final=True)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(CaptureFailureAlert.objects.exists())

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_pair_open_for_the_threshold_days_or_more_sends_exactly_one_alert(self, mock_fetch):
        """Regressao critica: sem o piso de dias, todo par aberto (a maioria e so um concurso
        ainda nao sorteado, nao uma falha real -- ver Intent da spec) dispararia alerta todo dia,
        inundando o operador. So dispara a partir de CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS."""
        self._create_stale_bet()
        mock_fetch.return_value = None
        fetch_daily_results(final=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Quina', mail.outbox[0].subject)
        self.assertIn('999', mail.outbox[0].subject)
        self.assertTrue(CaptureFailureAlert.objects.filter(game='Quina', contest='999').exists())

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_rerunning_final_for_the_same_pair_does_not_resend_the_alert(self, mock_fetch):
        self._create_stale_bet()
        mock_fetch.return_value = None
        fetch_daily_results(final=True)
        fetch_daily_results(final=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(CaptureFailureAlert.objects.filter(game='Quina', contest='999').count(), 1)

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_multiple_stale_pairs_send_one_alert_email_each_not_an_aggregate(self, mock_fetch):
        self._create_stale_bet(game='Quina', contest='999')
        self._create_stale_bet(game='Lotofacil', contest='888')
        mock_fetch.return_value = None
        fetch_daily_results(final=True)
        self.assertEqual(len(mail.outbox), 2)
        subjects = {email.subject for email in mail.outbox}
        self.assertTrue(any('Quina' in s and '999' in s for s in subjects))
        self.assertTrue(any('Lotofacil' in s and '888' in s for s in subjects))

    @override_settings(OPERATOR_ALERT_EMAIL='')
    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_missing_operator_email_does_not_raise_and_does_not_send(self, mock_fetch):
        self._create_stale_bet()
        mock_fetch.return_value = None
        result = fetch_daily_results(final=True)
        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(CaptureFailureAlert.objects.exists())

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_missing_operator_email_does_not_permanently_silence_the_alert(self, mock_fetch):
        """Regressao critica encontrada na revisao: gravar CaptureFailureAlert incondicionalmente
        (antes de confirmar o envio) faria uma OPERATOR_ALERT_EMAIL esquecida no primeiro deploy
        silenciar o alerta desse par pra sempre, mesmo depois de configurada corretamente. O
        registro so pode acontecer apos uma entrega real confirmada."""
        self._create_stale_bet()
        mock_fetch.return_value = None

        with override_settings(OPERATOR_ALERT_EMAIL=''):
            fetch_daily_results(final=True)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(CaptureFailureAlert.objects.exists())

        fetch_daily_results(final=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(CaptureFailureAlert.objects.filter(game='Quina', contest='999').exists())

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_stale_capture_failure_never_creates_a_hit_notification(self, mock_fetch):
        self._create_stale_bet()
        mock_fetch.return_value = None
        fetch_daily_results(final=True)
        self.assertFalse(HitNotification.objects.exists())

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_failure_in_one_pair_capture_does_not_block_alert_evaluation_of_another(self, mock_fetch):
        """Confirma o isolamento ja existente da Story 2.1 no loop de CAPTURA -- nao exercita o
        try/except novo desta story (ver test_exception_evaluating_one_pairs_alert_does_not_block_another
        pra isso)."""
        self._create_stale_bet(game='Quina', contest='999')
        self._create_stale_bet(game='Lotofacil', contest='888')

        def side_effect(game, contest):
            if game == 'Quina':
                raise Exception('falha simulada de scraping')
            return None

        mock_fetch.side_effect = side_effect
        fetch_daily_results(final=True)
        self.assertTrue(CaptureFailureAlert.objects.filter(game='Quina', contest='999').exists())
        self.assertTrue(CaptureFailureAlert.objects.filter(game='Lotofacil', contest='888').exists())

    @patch('apps.loterias_core.jobs.send_capture_failure_alert')
    def test_exception_evaluating_one_pairs_alert_does_not_block_another(self, mock_send_alert):
        """Exercita o try/except de _alert_operator_of_stale_capture_failures em si (nao o loop de
        captura pre-existente da Story 2.1) -- uma excecao ao avaliar/enviar o alerta de um par
        nao pode impedir o par seguinte de ser avaliado."""
        self._create_stale_bet(game='Quina', contest='999')
        self._create_stale_bet(game='Lotofacil', contest='888')

        def side_effect(game, contest):
            if game == 'Quina':
                raise Exception('falha simulada ao enviar')
            return True

        mock_send_alert.side_effect = side_effect
        _alert_operator_of_stale_capture_failures([('Quina', '999'), ('Lotofacil', '888')])
        self.assertFalse(CaptureFailureAlert.objects.filter(game='Quina', contest='999').exists())
        self.assertTrue(CaptureFailureAlert.objects.filter(game='Lotofacil', contest='888').exists())

    def test_alert_based_on_the_oldest_bet_when_multiple_bets_exist_for_the_pair(self):
        """order_by('created_at') tem que escolher o MAIS ANTIGO entre varios bets do mesmo par,
        nao o unico/mais recente -- um bug usando .last() ou omitindo o order_by passaria
        despercebido se so existisse 1 bet por par em todo teste."""
        old_bet = self._create_stale_bet(game='Quina', contest='999', days_old=CAPTURE_FAILURE_ALERT_THRESHOLD_DAYS)
        self._create_stale_bet(game='Quina', contest='999', days_old=1)
        _alert_operator_of_stale_capture_failures([('Quina', '999')])
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(CaptureFailureAlert.objects.filter(game='Quina', contest='999').exists())

    def test_pair_resolved_during_this_run_is_not_alerted(self):
        """Reconsulta LotteryResult (nao so o snapshot congelado de open_pairs) antes de alertar
        -- um par que foi resolvido por uma verificacao manual (check_bet_result_view) durante a
        janela desta mesma execucao do cron nao pode gerar um alerta de 'falha' obsoleto."""
        self._create_stale_bet(game='Quina', contest='999')
        LotteryResult.objects.create(
            game='Quina', contest='999', numbers=[1, 2, 3, 4, 5], clovers=[], prizes={},
        )
        _alert_operator_of_stale_capture_failures([('Quina', '999')])
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(CaptureFailureAlert.objects.exists())

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_three_daily_runs_retry_automatically_and_alert_only_on_final(self, mock_fetch):
        """Simula o ciclo real de cron (3h/3h15/3h30): 2 tentativas sem --final, depois a
        --final -- confirma que o retry automatico (idempotente, sem logica nova) e a avaliacao
        de alerta (so na ultima) funcionam juntas na sequencia real, nao so isoladamente."""
        self._create_stale_bet()
        mock_fetch.return_value = None

        fetch_daily_results(final=False)
        self.assertEqual(len(mail.outbox), 0)
        fetch_daily_results(final=False)
        self.assertEqual(len(mail.outbox), 0)
        fetch_daily_results(final=True)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(CaptureFailureAlert.objects.filter(game='Quina', contest='999').exists())

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_final_flag_command_integration_still_evaluates_alerts(self, mock_fetch):
        """Integra com o management command real (nao mockado) -- confirma que --final chega
        ate a avaliacao de alerta, nao so que o parametro e repassado (ja coberto por
        FetchDailyResultsCommandTests com o job mockado)."""
        self._create_stale_bet()
        mock_fetch.return_value = None
        call_command('fetch_daily_results', '--final')
        self.assertEqual(len(mail.outbox), 1)
