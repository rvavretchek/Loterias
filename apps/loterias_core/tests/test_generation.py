import itertools
import json
import re
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from io import StringIO
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
    GenerationRule, RULE_NAMES_BY_GAME, RULE_DEFINITIONS, GAME_GRID,
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
    generate_bet_with_relaxation,
    normalize_numbers,
    check_duplicate_bet,
    suggest_next_contest,
    apply_prize_to_bet,
    normalize_contest,
    bet_satisfies_rules,
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

    def test_saves_contest_normalized_without_leading_zeros(self):
        """Story 2.12: '02500' e o mesmo concurso real que '2500' -- grava sempre normalizado."""
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '02500'})
        bet = GeneratedBet.objects.get(user=self.user)
        self.assertEqual(bet.contest, '2500')
        self.assertRedirects(response, reverse('bet_detail', args=[bet.pk]))

    def test_blocks_leading_zero_spelling_of_already_drawn_contest(self):
        """Story 2.12: '02500' normaliza pra '2500' antes do bloqueio -- duas grafias do mesmo
        concurso real nunca furam a checagem de concurso ja sorteado."""
        LotteryResult.objects.create(game='Mega-sena', contest='2500', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '02500'}, follow=True)
        self.assertEqual(GeneratedBet.objects.count(), 0)
        self.assertRedirects(response, reverse('home'))

    def test_leading_zero_spelling_is_normalized_and_allows_multiple_bets_per_contest(self):
        """Story 2.12 + 2.20: '02500' normaliza pra '2500'; o usuario pode gerar varios jogos pro mesmo Jogo+Concurso."""
        GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='2500',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '02500'}, follow=True)
        bets = GeneratedBet.objects.filter(user=self.user, game='Mega-sena')
        self.assertEqual(bets.count(), 2)
        self.assertEqual(set(bets.values_list('contest', flat=True)), {'2500'})

    def test_user_can_generate_many_bets_for_the_same_game_and_contest(self):
        """Story 2.20: sem limite de jogos por Jogo+Concurso (ate o concurso ser sorteado)."""
        for _ in range(3):
            response = self.client.post(reverse('create_bet'), {'jogo': 'Quina', 'concurso': '6000'}, follow=True)
            mensagens = [m.level_tag for m in response.context['messages']]
            self.assertNotIn('error', mensagens)
        self.assertEqual(GeneratedBet.objects.filter(user=self.user, game='Quina', contest='6000').count(), 3)

    def test_blocks_already_drawn_contest_even_when_user_has_a_bet_for_it(self):
        """O bloqueio de concurso ja sorteado vale mesmo com um GeneratedBet do proprio usuario
        pro mesmo Jogo+Concurso: nenhum registro novo e criado."""
        LotteryResult.objects.create(game='Mega-sena', contest='2500', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='2500',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '2500'}, follow=True)
        self.assertEqual(GeneratedBet.objects.filter(user=self.user).count(), 1)
        mensagens = [(m.message, m.level_tag) for m in response.context['messages']]
        self.assertEqual(mensagens, [('O concurso 2500 de Mega-sena ja foi sorteado. Escolha outro concurso.', 'error')])

    def test_allows_numeric_contest_without_lottery_result(self):
        """Story 2.12: mesmo um concurso especial/comemorativo (ex. Mega da Virada) tem um numero
        de concurso ordinario e numerico na CEF -- nao existe concurso genuinamente alfanumerico.
        Este teste confirma que um concurso numerico sem LotteryResult ainda (nao sorteado ainda)
        continua sendo aceito normalmente."""
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '9999'})
        self.assertEqual(GeneratedBet.objects.filter(user=self.user).count(), 1)

    def test_rejects_non_numeric_contest(self):
        """Story 2.12: concurso nao numerico e sempre invalido -- nunca gravado."""
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': 'ESPECIAL-2026'}, follow=True)
        self.assertEqual(GeneratedBet.objects.count(), 0)
        self.assertRedirects(response, reverse('home'))
        mensagens = [(m.message, m.level_tag) for m in response.context['messages']]
        self.assertIn(('Numero de concurso invalido: ESPECIAL-2026.', 'error'), mensagens)

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

    def test_api_create_bet_rejects_invalid_game(self):
        """Story 2.13: jogo invalido devolve 400 claro, nunca um 500 nao tratado."""
        response = self.client.post(
            reverse('api_create_bet'),
            data=json.dumps({'jogo': 'Nao-Existe', 'concurso': '2500'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Jogo invalido')

    def test_api_create_bet_rejects_unhashable_game_type(self):
        """Story 2.13: 'in GAMES_CONFIG' quebraria com TypeError pra um tipo nao-hasheavel (ex. lista)
        -- checagem de tipo evita o mesmo 500 nao tratado que a story existe pra fechar."""
        response = self.client.post(
            reverse('api_create_bet'),
            data=json.dumps({'jogo': ['Mega-sena'], 'concurso': '2500'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Jogo invalido')

    def test_api_create_bet_rejects_non_numeric_contest(self):
        """Story 2.12: api_create_bet_view tambem normaliza/rejeita, mesmo endpoint de preview."""
        response = self.client.post(
            reverse('api_create_bet'),
            data=json.dumps({'jogo': 'Quina', 'concurso': 'ESPECIAL-2026'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Numero de concurso invalido: ESPECIAL-2026')

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

    def test_allows_multiple_manual_bets_for_same_contest_and_user(self):
        """Story 2.20: guardar varios jogos manuais pro mesmo Jogo+Concurso e permitido."""
        GeneratedBet.objects.create(
            user=self.user, game='Lotofacil', contest='3000',
            numbers=self.numbers, clovers=[], sequential_pairs=0, manual=True,
        )
        response = self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Lotofacil',
            'concurso': '3000',
            'numeros': self.numeros_str,
        }, follow=True)
        self.assertEqual(GeneratedBet.objects.filter(user=self.user, game='Lotofacil', contest='3000').count(), 2)
        mensagens = [m.level_tag for m in response.context['messages']]
        self.assertNotIn('error', mensagens)

    def test_blocks_contest_that_already_has_lottery_result(self):
        LotteryResult.objects.create(game='Lotofacil', contest='3000', numbers=self.numbers, clovers=[], prizes={})
        response = self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Lotofacil',
            'concurso': '3000',
            'numeros': self.numeros_str,
        }, follow=True)
        self.assertEqual(GeneratedBet.objects.count(), 0)
        mensagens = [(m.message, m.level_tag) for m in response.context['messages']]
        self.assertEqual(mensagens, [('O concurso 3000 de Lotofacil ja foi sorteado. Escolha outro concurso.', 'error')])

    def test_blocks_leading_zero_spelling_of_already_drawn_contest(self):
        """Story 2.12: '03000' normaliza pra '3000' antes do bloqueio."""
        LotteryResult.objects.create(game='Lotofacil', contest='3000', numbers=self.numbers, clovers=[], prizes={})
        response = self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Lotofacil',
            'concurso': '03000',
            'numeros': self.numeros_str,
        })
        self.assertEqual(GeneratedBet.objects.count(), 0)
        self.assertRedirects(response, reverse('home'))

    @patch('apps.loterias_core.views.fetch_cef_result')
    def test_saves_contest_normalized_without_leading_zeros(self, mock_fetch):
        mock_fetch.return_value = None
        self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Lotofacil',
            'concurso': '03000',
            'numeros': self.numeros_str,
        })
        bet = GeneratedBet.objects.get(user=self.user)
        self.assertEqual(bet.contest, '3000')

    @patch('apps.loterias_core.views.fetch_cef_result')
    def test_allows_numeric_contest_without_lottery_result(self, mock_fetch):
        """Story 2.12: mesmo um concurso especial/comemorativo (ex. Mega da Virada) tem um numero
        de concurso ordinario e numerico na CEF -- nao existe concurso genuinamente alfanumerico."""
        mock_fetch.return_value = None
        response = self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Lotofacil',
            'concurso': '9999',
            'numeros': self.numeros_str,
        })
        self.assertEqual(GeneratedBet.objects.filter(user=self.user).count(), 1)

    def test_rejects_non_numeric_contest(self):
        """Story 2.12: concurso nao numerico e sempre invalido -- nunca gravado."""
        response = self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Lotofacil',
            'concurso': 'ESPECIAL-2026',
            'numeros': self.numeros_str,
        }, follow=True)
        self.assertEqual(GeneratedBet.objects.count(), 0)
        self.assertRedirects(response, reverse('home'))
        mensagens = [(m.message, m.level_tag) for m in response.context['messages']]
        self.assertIn(('Numero de concurso invalido: ESPECIAL-2026.', 'error'), mensagens)

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


class RegenerateBetViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='regen@example.com', password='SenhaForte123')
        self.client.force_login(self.user)
        self.bet = GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='5000',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=1,
        )

    def test_regenerating_bet_replaces_original_in_place(self):
        """Story 2.17: Refazer substitui o jogo original in-place -- nunca cria um segundo
        GeneratedBet pro mesmo Jogo+Concurso ("Refazer" troca os numeros do jogo)."""
        original_numbers = list(self.bet.numbers)
        response = self.client.get(reverse('regenerate_bet', args=[self.bet.pk]))
        self.assertEqual(
            GeneratedBet.objects.filter(user=self.user, game='Mega-sena', contest='5000').count(), 1
        )
        self.bet.refresh_from_db()
        self.assertRedirects(response, reverse('bet_detail', args=[self.bet.pk]))
        self.assertNotEqual(self.bet.numbers, original_numbers)
        self.assertEqual(self.bet.sequential_pairs, count_sequential_pairs(self.bet.numbers))

    @patch('apps.loterias_core.views.generate_bet_with_relaxation')
    def test_regenerating_replaces_clovers_for_game_with_clovers(self, mock_generate_bet):
        """Story 2.17: jogo com trevos (Milionaria) tem os trevos tambem substituidos, nao so os
        numeros -- cobre o campo que a Mega-sena (sem trevo) nao consegue exercitar. Mocka
        generate_bet pra evitar teste instavel (o pool de trevos da Milionaria tem so 15
        combinacoes possiveis, entao um novo sorteio coincidir com o antigo nao e tao raro)."""
        bet = GeneratedBet.objects.create(
            user=self.user, game='Milionaria', contest='6000',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[1, 2], sequential_pairs=0,
        )
        mock_generate_bet.return_value = ([10, 20, 30, 40, 45, 50], [3, 4], None)
        self.client.get(reverse('regenerate_bet', args=[bet.pk]))
        bet.refresh_from_db()
        self.assertEqual(bet.clovers, [3, 4])

    def test_regenerating_resets_manual_and_verification_fields(self):
        """Story 2.17: um jogo manual ja verificado (result_checked/hits/prize/manual) vira um jogo
        algoritmico novo apos Refazer -- nenhum desses campos pode sobreviver ao numero antigo."""
        checked_bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='6001',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
            manual=True, result_checked=True, hits=3, prize=50, prize_description='quadra',
        )
        self.client.get(reverse('regenerate_bet', args=[checked_bet.pk]))
        checked_bet.refresh_from_db()
        self.assertFalse(checked_bet.manual)
        self.assertFalse(checked_bet.result_checked)
        self.assertEqual(checked_bet.hits, 0)
        self.assertEqual(checked_bet.prize, 0)
        self.assertEqual(checked_bet.prize_description, '')

    def test_blocks_regenerating_for_contest_that_already_has_lottery_result(self):
        """Story 6.3: alem da contagem nao mudar, o jogo original precisa ficar intocado -- uma
        contagem igual sozinha nao provaria que 'Refazer' nao trocou os numeros da mesma linha."""
        LotteryResult.objects.create(game='Mega-sena', contest='5000', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        original_numbers = list(self.bet.numbers)
        response = self.client.get(reverse('regenerate_bet', args=[self.bet.pk]), follow=True)
        self.assertEqual(GeneratedBet.objects.filter(user=self.user, game='Mega-sena', contest='5000').count(), 1)
        self.assertRedirects(response, reverse('bet_detail', args=[self.bet.pk]), target_status_code=200)
        self.bet.refresh_from_db()
        self.assertEqual(self.bet.numbers, original_numbers)
        mensagens = [(m.message, m.level_tag) for m in response.context['messages']]
        self.assertEqual(mensagens, [('O concurso 5000 de Mega-sena ja foi sorteado. Escolha outro concurso.', 'error')])


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


class RuleNamesByGameTests(TestCase):
    def test_keys_match_games_config_and_names_are_defined(self):
        self.assertEqual(set(RULE_NAMES_BY_GAME), set(GAMES_CONFIG))
        for names in RULE_NAMES_BY_GAME.values():
            self.assertEqual(len(names), len(set(names)))
            for name in names:
                self.assertIn(name, RULE_DEFINITIONS)

    def test_row_and_column_rules_for_every_game_with_a_grid_except_lotomania(self):
        for game in ('Mega-sena', 'Milionaria', 'Quina', 'Dupla-Sena', 'Lotofacil'):
            self.assertIn('limit_row_count', RULE_NAMES_BY_GAME[game])
            self.assertIn('limit_column_count', RULE_NAMES_BY_GAME[game])
            self.assertIn(game, GAME_GRID)
        self.assertNotIn('limit_row_count', RULE_NAMES_BY_GAME['Lotomania'])
        self.assertNotIn('limit_column_count', RULE_NAMES_BY_GAME['Lotomania'])

    def test_rule_counts_match_the_boss_lists(self):
        counts = {game: len(names) for game, names in RULE_NAMES_BY_GAME.items()}
        self.assertEqual(counts, {
            'Mega-sena': 5, 'Milionaria': 5, 'Quina': 5, 'Dupla-Sena': 5, 'Lotofacil': 7, 'Lotomania': 3,
        })


class GenerationRuleModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='rule-model@example.com', password='SenhaForte123')

    def test_unique_per_user_game_rule(self):
        GenerationRule.objects.create(user=self.user, game='Quina', rule_name='limit_sequence_count', enabled=True, numeric_value=2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            GenerationRule.objects.create(user=self.user, game='Quina', rule_name='limit_sequence_count')

    def test_check_constraint_rejects_both_values(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            GenerationRule.objects.create(
                user=self.user, game='Quina', rule_name='distribution_type',
                numeric_value=1, choice_value='homogenea',
            )

    def test_disabled_row_without_value_is_allowed(self):
        rule = GenerationRule.objects.create(user=self.user, game='Quina', rule_name='limit_sequence_count')
        self.assertFalse(rule.enabled)
        self.assertIsNone(rule.numeric_value)

    def test_clean_rejects_rule_name_from_another_game(self):
        rule = GenerationRule(user=self.user, game='Lotomania', rule_name='limit_row_count')
        with self.assertRaises(ValidationError):
            rule.clean()

    def test_check_constraint_rejects_numeric_value_zero(self):
        """Fronteira (feedback do Boss, 2026-09-25): 0 numeros permitidos por linha/coluna e
        matematicamente impossivel de satisfazer (todo numero sorteado cai em alguma linha e
        coluna) -- o minimo valido pra qualquer regra numerica e 1, sempre."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            GenerationRule.objects.create(
                user=self.user, game='Quina', rule_name='limit_row_count',
                enabled=True, numeric_value=0,
            )

    def test_check_constraint_rejects_negative_numeric_value(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            GenerationRule.objects.create(
                user=self.user, game='Quina', rule_name='limit_column_count',
                enabled=True, numeric_value=-1,
            )

    def test_clean_rejects_numeric_value_below_one(self):
        rule = GenerationRule(user=self.user, game='Quina', rule_name='limit_row_count', numeric_value=0)
        with self.assertRaises(ValidationError):
            rule.clean()


class GenerationRulesEditScreenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='rules@example.com', password='SenhaForte123')
        self.other = User.objects.create_user(email='rules-other@example.com', password='SenhaForte123')
        self.url = reverse('generation_rules', kwargs={'jogo': 'mega-sena'})
        self.client.force_login(self.user)

    def _post(self, data, url=None):
        return self.client.post(url or self.url, data)

    def test_anonymous_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_unknown_game_is_404(self):
        response = self.client.get(reverse('generation_rules', kwargs={'jogo': 'xpto'}))
        self.assertEqual(response.status_code, 404)

    def test_every_rule_has_an_explanation_associated_via_aria_describedby(self):
        """Story 7.2 (FR-30/UX-DR11): as 7 regras possiveis tem explicacao em linguagem comum,
        nao so o rotulo curto -- Lotofacil tem o conjunto completo das 7."""
        url = reverse('generation_rules', kwargs={'jogo': 'lotofacil'})
        response = self.client.get(url)
        html = response.content.decode()
        for name in RULE_NAMES_BY_GAME['Lotofacil']:
            self.assertIn(f'aria-describedby="help-{name}"', html)
            explanation = RULE_DEFINITIONS[name]['explanation']
            self.assertContains(response, explanation)

    def test_first_visit_shows_default_with_disabled_value_fields(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usando regras padrão do sistema')
        self.assertNotContains(response, 'data-open-dialog="modal-restaurar"')
        for name in RULE_NAMES_BY_GAME['Mega-sena']:
            self.assertContains(response, f'name="value_{name}"')
        self.assertContains(response, 'aria-describedby="help-limit_row_count"')
        self.assertFalse(GenerationRule.objects.exists())
        html = response.content.decode()
        for name in RULE_NAMES_BY_GAME['Mega-sena']:
            field = html[html.index('id="value-%s"' % name):]
            field = field[:field.index('>')]
            self.assertIn('disabled', field, name)

    def test_enabled_rule_renders_editable_value_and_restore_modal_when_customized(self):
        self._post({'enabled_limit_sequence_count': 'on', 'value_limit_sequence_count': '2'})
        html = self.client.get(self.url).content.decode()
        enabled_field = html[html.index('id="value-limit_sequence_count"'):]
        self.assertNotIn('disabled', enabled_field[:enabled_field.index('>')])
        disabled_field = html[html.index('id="value-limit_sequence_pairs"'):]
        self.assertIn('disabled', disabled_field[:disabled_field.index('>')])
        self.assertIn('data-open-dialog="modal-restaurar"', html)
        self.assertIn('name="restaurar"', html)

    def test_save_writes_one_row_per_rule_and_shows_customized(self):
        response = self._post({
            'enabled_limit_sequence_count': 'on', 'value_limit_sequence_count': '2',
            'enabled_distribution_type': 'on', 'value_distribution_type': 'homogenea',
        })
        self.assertRedirects(response, self.url)
        rows = GenerationRule.objects.filter(user=self.user, game='Mega-sena')
        self.assertEqual(rows.count(), len(RULE_NAMES_BY_GAME['Mega-sena']))
        self.assertEqual(rows.get(rule_name='limit_sequence_count').numeric_value, 2)
        self.assertTrue(rows.get(rule_name='limit_sequence_count').enabled)
        self.assertEqual(rows.get(rule_name='distribution_type').choice_value, 'homogenea')
        self.assertFalse(rows.get(rule_name='limit_row_count').enabled)
        response = self.client.get(self.url)
        self.assertContains(response, 'Personalizado por você')
        self.assertContains(response, 'value="2"')

    def test_unchecking_keeps_row_disabled_and_preserves_value(self):
        self._post({'enabled_limit_sequence_count': 'on', 'value_limit_sequence_count': '3'})
        # Toggle desligado: o navegador nao envia o campo desabilitado.
        self._post({})
        rule = GenerationRule.objects.get(user=self.user, game='Mega-sena', rule_name='limit_sequence_count')
        self.assertFalse(rule.enabled)
        self.assertEqual(rule.numeric_value, 3)
        self.assertEqual(GenerationRule.objects.filter(user=self.user, game='Mega-sena').count(), 5)

    def test_invalid_values_save_nothing_and_show_range_error(self):
        for bad in ('', '0', '61', '2.5', 'abc', '-1'):
            response = self._post({'enabled_limit_sequence_count': 'on', 'value_limit_sequence_count': bad})
            self.assertEqual(response.status_code, 200, bad)
            self.assertContains(response, 'entre 1 e 60', msg_prefix=bad)
            self.assertFalse(GenerationRule.objects.exists(), bad)

    def test_huge_digit_string_is_a_validation_error_not_a_crash(self):
        response = self._post({'enabled_limit_sequence_count': 'on', 'value_limit_sequence_count': '9' * 5000})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'entre 1 e 60')
        self.assertFalse(GenerationRule.objects.exists())

    def test_invalid_post_preserves_what_the_user_typed(self):
        response = self._post({
            'enabled_limit_sequence_count': 'on', 'value_limit_sequence_count': '2',
            'enabled_limit_sequence_pairs': 'on', 'value_limit_sequence_pairs': '99',
        })
        self.assertContains(response, 'entre 1 e 60')
        html = response.content.decode()
        self.assertIn('value="2"', html)
        self.assertIn('value="99"', html)

    def test_invalid_choice_is_rejected(self):
        response = self._post({'enabled_distribution_type': 'on', 'value_distribution_type': 'xyz'})
        self.assertContains(response, 'Escolha um tipo de distribuição.')
        self.assertFalse(GenerationRule.objects.exists())

    def test_restore_deletes_only_this_user_and_game(self):
        self._post({'enabled_limit_sequence_count': 'on', 'value_limit_sequence_count': '2'})
        GenerationRule.objects.create(user=self.user, game='Quina', rule_name='limit_sequence_count')
        GenerationRule.objects.create(user=self.other, game='Mega-sena', rule_name='limit_sequence_count')
        response = self._post({'restaurar': '1'})
        self.assertRedirects(response, self.url)
        self.assertFalse(GenerationRule.objects.filter(user=self.user, game='Mega-sena').exists())
        self.assertTrue(GenerationRule.objects.filter(user=self.user, game='Quina').exists())
        self.assertTrue(GenerationRule.objects.filter(user=self.other, game='Mega-sena').exists())

    def test_users_are_isolated(self):
        GenerationRule.objects.create(
            user=self.other, game='Mega-sena', rule_name='limit_sequence_count', enabled=True, numeric_value=4,
        )
        response = self.client.get(self.url)
        self.assertContains(response, 'Usando regras padrão do sistema')
        self._post({'enabled_limit_sequence_count': 'on', 'value_limit_sequence_count': '2'})
        self.assertEqual(
            GenerationRule.objects.get(user=self.other, game='Mega-sena', rule_name='limit_sequence_count').numeric_value, 4,
        )

    def test_sequence_protection_modal_only_for_sequence_games(self):
        self.assertContains(self.client.get(self.url), 'id="modal-sem-sequencia"')
        lotomania = reverse('generation_rules', kwargs={'jogo': 'lotomania'})
        self.assertNotContains(self.client.get(lotomania), 'id="modal-sem-sequencia"')

    def test_row_column_fields_shown_for_quina_and_hidden_for_lotomania(self):
        quina = self.client.get(reverse('generation_rules', kwargs={'jogo': 'quina'}))
        self.assertContains(quina, 'name="value_limit_row_count"')
        self.assertContains(quina, 'name="value_limit_column_count"')
        self.assertContains(quina, '8 linhas x 10 colunas')
        lotomania = self.client.get(reverse('generation_rules', kwargs={'jogo': 'lotomania'}))
        self.assertNotContains(lotomania, 'limit_row_count')

    def test_home_links_to_rules_of_each_game(self):
        response = self.client.get(reverse('home'))
        for game in GAMES_CONFIG:
            self.assertContains(response, reverse('generation_rules', kwargs={'jogo': game.lower()}))


def _rule(name, value=None, enabled=True, choice=None):
    return GenerationRule(rule_name=name, numeric_value=value, choice_value=choice, enabled=enabled)


class BetSatisfiesRulesTests(TestCase):
    def test_no_rules_is_ok(self):
        self.assertEqual(bet_satisfies_rules([1, 2, 3, 4, 5, 6], [], 'Mega-sena', []), (True, []))

    def test_sequence_count_is_max_run_length(self):
        rules = [_rule('limit_sequence_count', 2)]
        self.assertTrue(bet_satisfies_rules([1, 2, 10, 20, 30, 40], [], 'Mega-sena', rules)[0])
        self.assertEqual(
            bet_satisfies_rules([1, 2, 3, 20, 30, 40], [], 'Mega-sena', rules),
            (False, ['limit_sequence_count']),
        )

    def test_sequence_count_one_forbids_any_pair(self):
        rules = [_rule('limit_sequence_count', 1)]
        self.assertFalse(bet_satisfies_rules([1, 2, 10, 20, 30, 40], [], 'Mega-sena', rules)[0])
        self.assertTrue(bet_satisfies_rules([1, 3, 10, 20, 30, 40], [], 'Mega-sena', rules)[0])

    def test_sequence_pairs_counts_runs(self):
        rules = [_rule('limit_sequence_pairs', 1)]
        self.assertTrue(bet_satisfies_rules([1, 2, 3, 20, 30, 40], [], 'Mega-sena', rules)[0])
        self.assertEqual(
            bet_satisfies_rules([1, 2, 20, 21, 40, 50], [], 'Mega-sena', rules)[1],
            ['limit_sequence_pairs'],
        )

    def test_row_and_column_limits(self):
        # Mega-sena 6x10: 1..10 e a linha 1; coluna 1 = 1, 11, 21...
        self.assertEqual(
            bet_satisfies_rules([1, 3, 5, 30, 40, 55], [], 'Mega-sena', [_rule('limit_row_count', 2)]),
            (False, ['limit_row_count']),
        )
        self.assertTrue(bet_satisfies_rules([1, 13, 25, 37, 49, 60], [], 'Mega-sena', [_rule('limit_row_count', 1)])[0])
        self.assertEqual(
            bet_satisfies_rules([1, 11, 21, 34, 45, 58], [], 'Mega-sena', [_rule('limit_column_count', 2)]),
            (False, ['limit_column_count']),
        )

    def test_quina_grid_is_8_rows_by_10(self):
        rules = [_rule('limit_row_count', 1)]
        self.assertFalse(bet_satisfies_rules([71, 72, 1, 15, 33], [], 'Quina', rules)[0])

    def test_homogeneous_requires_one_per_band(self):
        rules = [_rule('distribution_type', choice='homogenea')]
        self.assertTrue(bet_satisfies_rules([5, 15, 25, 35, 45, 55], [], 'Mega-sena', rules)[0])
        self.assertEqual(
            bet_satisfies_rules([1, 2, 25, 35, 45, 55], [], 'Mega-sena', rules)[1], ['distribution_type'],
        )

    def test_homogeneous_lotofacil_needs_three_per_row(self):
        rules = [_rule('distribution_type', choice='homogenea')]
        ok = [1, 2, 3, 6, 7, 8, 11, 12, 13, 16, 17, 18, 21, 22, 23]
        self.assertTrue(bet_satisfies_rules(ok, [], 'Lotofacil', rules)[0])
        self.assertFalse(bet_satisfies_rules(list(range(11, 26)), [], 'Lotofacil', rules)[0])

    def test_min_sequences(self):
        rules = [_rule('limit_min_sequences', 2)]
        self.assertFalse(bet_satisfies_rules([1, 2, 10, 20, 30], [], 'Lotofacil', rules)[0])
        self.assertEqual(
            bet_satisfies_rules([1, 5, 9, 13], [], 'Lotofacil', rules)[1], ['limit_min_sequences'],
        )
        self.assertTrue(bet_satisfies_rules([1, 2, 10, 11, 20], [], 'Lotofacil', rules)[0])

    def test_min_gap_between_sequences(self):
        rules = [_rule('limit_min_gap_between_sequences', 2)]
        # sequencias 1-2 e 4-5: 1 numero entre elas (3) -> viola
        self.assertEqual(
            bet_satisfies_rules([1, 2, 4, 5, 20], [], 'Lotofacil', rules)[1],
            ['limit_min_gap_between_sequences'],
        )
        self.assertTrue(bet_satisfies_rules([1, 2, 5, 6, 20], [], 'Lotofacil', rules)[0])
        # 0 ou 1 sequencia: satisfeita
        self.assertTrue(bet_satisfies_rules([1, 2, 10, 20], [], 'Lotofacil', rules)[0])
        self.assertTrue(bet_satisfies_rules([1, 5, 9], [], 'Lotofacil', rules)[0])

    def test_min_rules_ignored_without_value_or_disabled(self):
        rules = [_rule('limit_min_sequences', None), _rule('limit_min_gap_between_sequences', 5, enabled=False)]
        self.assertTrue(bet_satisfies_rules([1, 5, 9], [], 'Lotofacil', rules)[0])

    def test_random_distribution_never_violates(self):
        rules = [_rule('distribution_type', choice='totalmente_aleatoria')]
        self.assertTrue(bet_satisfies_rules([1, 2, 3, 4, 5, 6], [], 'Mega-sena', rules)[0])

    def test_returns_complete_list_of_violations(self):
        rules = [_rule('limit_sequence_count', 1), _rule('limit_row_count', 1)]
        ok, violated = bet_satisfies_rules([1, 2, 3, 4, 5, 6], [], 'Mega-sena', rules)
        self.assertFalse(ok)
        self.assertEqual(sorted(violated), ['limit_row_count', 'limit_sequence_count'])

    def test_ignores_disabled_valueless_and_unknown_rules(self):
        rules = [
            _rule('limit_sequence_count', 1, enabled=False),
            _rule('limit_sequence_pairs', None),
            _rule('unknown_rule', 5),
            _rule('limit_min_sequences', None),
        ]
        self.assertEqual(bet_satisfies_rules([1, 2, 3, 4, 5, 6], [], 'Mega-sena', rules), (True, []))


class GenerateBetWithRulesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='rules@example.com', password='SenhaForte123')

    def _save(self, name, value=None, enabled=True, choice=None, game='Mega-sena'):
        GenerationRule.objects.create(
            user=self.user, game=game, rule_name=name, numeric_value=value,
            choice_value=choice, enabled=enabled,
        )

    def test_custom_rules_are_always_satisfied(self):
        self._save('limit_sequence_count', 1)
        self._save('limit_row_count', 2)
        rules = list(GenerationRule.objects.filter(user=self.user))
        for _ in range(30):
            nums, _clovers = generate_bet('Mega-sena', self.user)
            self.assertEqual(len(nums), 6)
            self.assertTrue(bet_satisfies_rules(nums, [], 'Mega-sena', rules)[0])

    def test_customized_ignores_adaptive_sequence_rule(self):
        self._save('limit_sequence_pairs', 6, enabled=False)
        with patch('apps.loterias_core.utils.recent_bets_had_sequence') as recent:
            for _ in range(5):
                generate_bet('Mega-sena', self.user)
            recent.assert_not_called()

    def test_all_disabled_means_free_draw(self):
        for name in RULE_NAMES_BY_GAME['Quina']:
            self._save(name, None, enabled=False, game='Quina')
        with patch('apps.loterias_core.utils.recent_bets_had_sequence') as recent:
            nums, _ = generate_bet('Quina', self.user)
            recent.assert_not_called()
        self.assertEqual(len(nums), 5)

    def test_no_rows_keeps_adaptive_behavior(self):
        GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='1',
            numbers=[1, 2, 10, 20, 30, 40], clovers=[], sequential_pairs=1,
        )
        for _ in range(20):
            nums, _ = generate_bet('Mega-sena', self.user)
            self.assertEqual(count_sequential_pairs(nums), 0)

    def test_rules_of_other_game_do_not_apply(self):
        self._save('limit_sequence_count', 1, game='Quina')
        with patch('apps.loterias_core.utils.recent_bets_had_sequence', return_value=False) as recent:
            generate_bet('Mega-sena', self.user)
            recent.assert_called()

    def test_homogeneous_generation_one_per_band(self):
        self._save('distribution_type', choice='homogenea')
        for extra in ('Quina', 'Milionaria', 'Dupla-Sena'):
            self._save('distribution_type', choice='homogenea', game=extra)
        for game_name in ('Mega-sena', 'Quina', 'Milionaria', 'Dupla-Sena'):
            rules = list(GenerationRule.objects.filter(user=self.user, game=game_name))
            for _ in range(20):
                nums, _ = generate_bet(game_name, self.user)
                self.assertEqual(len(nums), GAMES_CONFIG[game_name]['bets_count'])
                self.assertEqual(len(set(nums)), len(nums))
                self.assertTrue(bet_satisfies_rules(nums, [], game_name, rules)[0])

    def test_homogeneous_lotofacil_generates_three_per_row(self):
        self._save('distribution_type', choice='homogenea', game='Lotofacil')
        for _ in range(20):
            nums, _ = generate_bet('Lotofacil', self.user)
            self.assertEqual(len(set(nums)), 15)
            for row in range(5):
                self.assertEqual(sum(1 for n in nums if row * 5 < n <= row * 5 + 5), 3)

    def test_lotofacil_min_sequences_and_gap_generation(self):
        self._save('limit_min_sequences', 3, game='Lotofacil')
        self._save('limit_min_gap_between_sequences', 1, game='Lotofacil')
        rules = list(GenerationRule.objects.filter(user=self.user, game='Lotofacil'))
        for _ in range(10):
            nums, _, relaxed = generate_bet_with_relaxation('Lotofacil', self.user)
            self.assertIsNone(relaxed)
            self.assertTrue(bet_satisfies_rules(nums, [], 'Lotofacil', rules)[0])

    def test_lotomania_generation_respects_its_three_rules(self):
        self._save('limit_sequence_count', 6, game='Lotomania')
        self._save('limit_min_sequences', 4, game='Lotomania')
        self._save('limit_min_gap_between_sequences', 1, game='Lotomania')
        rules = list(GenerationRule.objects.filter(user=self.user, game='Lotomania'))
        for _ in range(5):
            nums, _clovers, relaxed = generate_bet_with_relaxation('Lotomania', self.user)
            self.assertIsNone(relaxed)
            self.assertEqual(len(set(nums)), 50)
            self.assertTrue(bet_satisfies_rules(nums, [], 'Lotomania', rules)[0])

    def test_milionaria_still_returns_clovers(self):
        self._save('limit_sequence_count', 2, game='Milionaria')
        nums, clovers = generate_bet('Milionaria', self.user)
        self.assertEqual(len(clovers), 2)

    def test_impossible_rules_return_none(self):
        """Duas regras inatingiveis: relaxar UMA nao basta -- nunca relaxa uma segunda (Story 4.5).
        Lotofacil (grade 5x5, 15 numeros sorteados): 'no maximo 1 por linha/coluna' e
        matematicamente inatingivel (casa dos pombos) mesmo com o minimo valido de 1 -- 0 nao e
        mais um valor aceito pra numeric_value (constraint de banco, feedback do Boss 2026-09-25)."""
        self._save('limit_column_count', 1, game='Lotofacil')
        self._save('limit_row_count', 1, game='Lotofacil')
        self.assertEqual(generate_bet('Lotofacil', self.user), (None, None))
        self.assertEqual(generate_bet_with_relaxation('Lotofacil', self.user), (None, None, None))

    def test_relaxes_the_only_impossible_rule_in_memory(self):
        """Story 4.5 (FR-22): uma regra inatingivel e relaxada, o jogo sai e o banco nao muda."""
        self._save('limit_sequence_count', 3, game='Lotofacil')
        self._save('limit_row_count', 1, game='Lotofacil')
        nums, clovers, relaxed = generate_bet_with_relaxation('Lotofacil', self.user)
        self.assertEqual(len(nums), 15)
        self.assertEqual(relaxed, 'limit_row_count')
        self.assertTrue(GenerationRule.objects.get(user=self.user, rule_name='limit_row_count').enabled)
        self.assertEqual(GenerationRule.objects.get(user=self.user, rule_name='limit_row_count').numeric_value, 1)

    def test_relaxation_picks_newest_updated_at_among_violated_rules_only(self):
        from datetime import timedelta
        from unittest.mock import patch
        from django.utils import timezone
        self._save('limit_sequence_count', 1)
        self._save('limit_sequence_pairs', 1)
        self._save('limit_row_count', 5)  # a mais recente de todas, mas NAO violada
        base = timezone.now()
        for offset, name in enumerate(('limit_sequence_count', 'limit_sequence_pairs', 'limit_row_count')):
            GenerationRule.objects.filter(user=self.user, rule_name=name).update(updated_at=base + timedelta(minutes=offset))
        calls = []

        def fake_draw(config, game, rules, attempts=10000):
            calls.append([rule.rule_name for rule in rules])
            if len(calls) == 1:
                return None, ['limit_sequence_count', 'limit_sequence_pairs']
            return [1, 12, 23, 34, 45, 56], []

        with patch('apps.loterias_core.utils._draw_with_rules', side_effect=fake_draw):
            nums, _clovers, relaxed = generate_bet_with_relaxation('Mega-sena', self.user)
        self.assertEqual(relaxed, 'limit_sequence_pairs')
        self.assertEqual(sorted(calls[1]), ['limit_row_count', 'limit_sequence_count'])
        self.assertEqual(nums, [1, 12, 23, 34, 45, 56])

    def test_default_mode_never_relaxes_and_wrapper_keeps_two_values(self):
        nums, clovers, relaxed = generate_bet_with_relaxation('Mega-sena', self.user)
        self.assertIsNone(relaxed)
        self.assertEqual(len(generate_bet('Mega-sena', self.user)), 2)


class RelaxationViewsTests(TestCase):
    """Story 4.5: regra relaxada -> jogo gerado como sucesso + aviso nomeando regra e Jogo."""

    def setUp(self):
        self.user = User.objects.create_user(email='relax@example.com', password='SenhaForte123')
        self.client.force_login(self.user)
        # Lotofacil (grade 5x5, 15 numeros sorteados): 'no maximo 1 por linha' e matematicamente
        # inatingivel mesmo no minimo valido (1) -- 0 nao e mais aceito (constraint de banco,
        # feedback do Boss 2026-09-25), entao a regra "impossivel" de teste usa Lotofacil, nao
        # mais Mega-sena.
        GenerationRule.objects.create(
            user=self.user, game='Lotofacil', rule_name='limit_row_count', numeric_value=1, enabled=True,
        )
        self.expected = (
            "O jogo de Lotofacil foi gerado relaxando a regra "
            "'Limita quantidade de números na mesma linha do volante'"
        )

    def test_create_view_saves_bet_and_names_relaxed_rule(self):
        response = self.client.post(reverse('create_bet'), {'jogo': 'Lotofacil', 'concurso': '3000'}, follow=True)
        self.assertEqual(GeneratedBet.objects.filter(user=self.user).count(), 1)
        msgs = [(m.level_tag, m.message) for m in response.context['messages']]
        self.assertTrue(any(level == 'success' for level, _ in msgs))
        self.assertTrue(any(level == 'warning' and self.expected in text for level, text in msgs), msgs)

    def test_regenerate_view_replaces_bet_and_names_relaxed_rule(self):
        original_numbers = list(range(1, 16))
        bet = GeneratedBet.objects.create(
            user=self.user, game='Lotofacil', contest='3000', numbers=original_numbers, clovers=[],
        )
        response = self.client.get(reverse('regenerate_bet', args=[bet.pk]), follow=True)
        bet.refresh_from_db()
        self.assertNotEqual(bet.numbers, original_numbers)
        msgs = [(m.level_tag, m.message) for m in response.context['messages']]
        self.assertTrue(any(level == 'warning' and self.expected in text for level, text in msgs), msgs)

    def test_api_returns_bet_and_relaxed_rule_label(self):
        response = self.client.post(
            reverse('api_create_bet'), data=json.dumps({'jogo': 'Lotofacil', 'concurso': '3000'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body['numeros']), 15)
        self.assertEqual(body['regra_relaxada'], 'Limita quantidade de números na mesma linha do volante')

    def test_no_relaxation_message_without_conflict(self):
        GenerationRule.objects.filter(user=self.user).delete()
        response = self.client.post(reverse('create_bet'), {'jogo': 'Lotofacil', 'concurso': '3000'}, follow=True)
        self.assertFalse(any(m.level_tag == 'warning' for m in response.context['messages']))


class ImpossibleRulesAcrossViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='rv@example.com', password='SenhaForte123')
        self.client.force_login(self.user)
        # Lotofacil (grade 5x5, 15 numeros): linha E coluna com limite 1 sao ambas inatingiveis
        # sozinhas (casa dos pombos) -- relaxar uma nao basta, a outra continua impossivel.
        GenerationRule.objects.create(
            user=self.user, game='Lotofacil', rule_name='limit_column_count', numeric_value=1, enabled=True,
        )
        GenerationRule.objects.create(
            user=self.user, game='Lotofacil', rule_name='limit_row_count', numeric_value=1, enabled=True,
        )

    def test_create_view_warns_and_saves_nothing_when_impossible(self):
        response = self.client.post(reverse('create_bet'), {'jogo': 'Lotofacil', 'concurso': '3000'}, follow=True)
        self.assertEqual(GeneratedBet.objects.count(), 0)
        self.assertContains(response, 'com as suas regras de geracao')
        self.assertNotContains(response, 'apos muitas tentativas')

    def test_regenerate_view_keeps_bet_when_impossible(self):
        original_numbers = list(range(1, 16))
        bet = GeneratedBet.objects.create(
            user=self.user, game='Lotofacil', contest='3000', numbers=original_numbers, clovers=[],
        )
        response = self.client.get(reverse('regenerate_bet', args=[bet.pk]), follow=True)
        bet.refresh_from_db()
        self.assertEqual(bet.numbers, original_numbers)
        self.assertContains(response, 'com as suas regras de geracao')

    def test_api_returns_422_when_impossible(self):
        response = self.client.post(
            reverse('api_create_bet'),
            data=json.dumps({'jogo': 'Lotofacil', 'concurso': '3000'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn('regras de geracao', response.json()['error'])


class RepeatedBetsAllowedTests(TestCase):
    """Boss (2026-09-21): repetir o mesmo jogo no mesmo Concurso ou em varios Concursos e permitido."""

    def setUp(self):
        self.user = User.objects.create_user(email='repete@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    def test_same_numbers_can_be_saved_repeatedly_and_across_contests(self):
        fixed = ([1, 2, 3, 4, 5, 6], [], None)
        with patch('apps.loterias_core.views.generate_bet_with_relaxation', return_value=fixed):
            for contest in ('3000', '3000', '3001'):
                self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': contest})
        self.assertEqual(GeneratedBet.objects.filter(user=self.user, numbers=[1, 2, 3, 4, 5, 6]).count(), 3)

    def test_regenerate_can_return_same_numbers_as_another_bet(self):
        GeneratedBet.objects.create(user=self.user, game='Mega-sena', contest='1', numbers=[1, 2, 3, 4, 5, 6], clovers=[])
        bet = GeneratedBet.objects.create(user=self.user, game='Mega-sena', contest='2', numbers=[7, 8, 9, 10, 11, 12], clovers=[])
        with patch('apps.loterias_core.views.generate_bet_with_relaxation', return_value=([1, 2, 3, 4, 5, 6], [], None)):
            self.client.get(reverse('regenerate_bet', args=[bet.pk]))
        bet.refresh_from_db()
        self.assertEqual(bet.numbers, [1, 2, 3, 4, 5, 6])

    def test_regenerate_deletes_stale_hit_notification(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='5', numbers=[1, 2, 3, 4, 5], clovers=[],
            result_checked=True, hits=5, prize=Decimal('100'),
        )
        HitNotification.objects.create(bet=bet, won=True)
        self.client.get(reverse('regenerate_bet', args=[bet.pk]))
        self.assertFalse(HitNotification.objects.filter(bet=bet).exists())


class AllPossibleRuleCombinationsTests(TestCase):
    """Story 6.5 (FR-27): pra cada Jogo, testa TODAS as 2^n combinacoes de quais regras ficam
    ligadas (o eixo combinatorio real e tratavel), com um valor moderado por regra -- nao o
    produto cartesiano infinito de valores, so das combinacoes possiveis de liga/desliga."""

    MODERATE_VALUE = {
        'limit_sequence_count': 3,
        'limit_sequence_pairs': 2,
        'limit_row_count': 3,
        'limit_column_count': 3,
        'limit_min_gap_between_sequences': 1,
        'limit_min_sequences': 1,
    }

    def setUp(self):
        self.user = User.objects.create_user(email='combos6.5@example.com', password='SenhaForte123')

    def _rule_subsets(self, game):
        names = RULE_NAMES_BY_GAME[game]
        for size in range(len(names) + 1):
            for combo in itertools.combinations(names, size):
                yield combo

    def _save_combo(self, game, combo):
        GenerationRule.objects.filter(user=self.user, game=game).delete()
        for name in RULE_NAMES_BY_GAME[game]:
            enabled = name in combo
            kind = RULE_DEFINITIONS[name]['kind']
            GenerationRule.objects.create(
                user=self.user, game=game, rule_name=name, enabled=enabled,
                numeric_value=self.MODERATE_VALUE[name] if kind == 'int' else None,
                choice_value='totalmente_aleatoria' if kind == 'choice' else None,
            )

    def test_every_rule_subset_is_satisfied_or_relaxes_at_most_one(self):
        for game in GAMES_CONFIG:
            active_names = RULE_NAMES_BY_GAME[game]
            for combo in self._rule_subsets(game):
                self._save_combo(game, combo)
                rules = list(GenerationRule.objects.filter(user=self.user, game=game, enabled=True))
                numbers, clovers, relaxed = generate_bet_with_relaxation(game, self.user)
                if numbers is None:
                    # Combinacao apertada demais pra sair por sorteio uniforme dentro do
                    # orcamento de tentativas, mesmo relaxando 1 regra -- comportamento definido
                    # (AD-12), nao e falha desta story: so confere que ninguem travou nem devolveu
                    # jogo invalido.
                    self.assertIsNone(clovers)
                    self.assertIsNone(relaxed)
                    continue
                if relaxed is None:
                    ok, violated = bet_satisfies_rules(numbers, clovers, game, rules)
                    self.assertTrue(ok, f'{game} {combo} violou regras ligadas sem relaxar: {violated}')
                else:
                    self.assertIn(relaxed, combo, f'{game} {combo} relaxou regra fora do combo: {relaxed}')
                    reduced = [r for r in rules if r.rule_name != relaxed]
                    ok, violated = bet_satisfies_rules(numbers, clovers, game, reduced)
                    self.assertTrue(ok, f'{game} {combo} relaxou {relaxed} mas ainda violou: {violated}')
