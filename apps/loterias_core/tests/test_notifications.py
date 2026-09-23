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

    def test_dupla_sena_notification_uses_second_draw_when_it_pays_more(self):
        """Story 2.18, ponta a ponta: bet que so bate no 2o sorteio da Dupla-Sena (premio maior que
        o 1o) gera HitNotification com o hits/premio do 2o sorteio, passando por
        fetch_daily_results -> _notify_covered_bets -> calculate_bet_prize -- nao so a unidade
        isolada de calculate_bet_prize."""
        bet = GeneratedBet.objects.create(
            user=self.user, game='Dupla-Sena', contest='3007',
            numbers=[9, 23, 32, 33, 39, 48], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Dupla-Sena', contest='3007',
            numbers=[10, 24, 26, 31, 32, 48],
            numbers_second_draw=[9, 23, 32, 33, 39, 48],
            clovers=[],
            prizes={'1': {'value': 'R$ 0,00', 'winners': 0}},
            prizes_second_draw={'6': {'value': 'R$ 500.000,00', 'winners': 1}},
        )
        with patch('apps.loterias_core.jobs.fetch_cef_result') as mock_fetch:
            mock_fetch.return_value = None
            fetch_daily_results()
        bet.refresh_from_db()
        self.assertEqual(bet.hits, 6)
        self.assertEqual(bet.prize, Decimal('500000.00'))
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
        self.assertNotContains(response, 'lq-bell')

    def test_badge_shown_with_unread_notification(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='5',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=bet, won=False)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'lq-bell')
        self.assertContains(response, reverse('notifications'))
        self.assertEqual(response.context['unread_notifications_count'], 1)
        self.assertContains(response, 'lq-bell-count')

    def test_badge_uses_success_color_when_won_notification_pending(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='6',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=bet, won=True)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'lq-bell-count is-win')

    def test_badge_appears_on_other_pages_too(self):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='7',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=bet, won=False)
        response = self.client.get(reverse('history'))
        self.assertContains(response, 'lq-bell')


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
        self.assertContains(response, 'Concurso 100')
        self.assertContains(response, 'Concurso 200')
        self.assertContains(response, 'lq-status-win')
        self.assertContains(response, 'Sem prêmio')

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
        self.assertContains(response, 'lq-ball-hit', count=2)
        rendered_numbers = re.findall(
            r'lq-ball-hit"[^>]*>\s*(\d{2})\s*<', response.content.decode()
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
        self.assertNotContains(response, 'lq-ball-hit')

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
        self.assertContains(response, 'Marcar como lida')


class MarkNotificationReadViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='marcarlida@example.com', password='SenhaForte123')
        self.client.force_login(self.user)
        self.bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='20',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        self.notification = HitNotification.objects.create(bet=self.bet, won=True)

    def test_next_url_only_redirects_to_same_site(self):
        url = reverse('mark_notification_read', args=[self.notification.pk])
        for evil in ('//evil.example/x', 'https://evil.example/x', '/\evil.example'):
            response = self.client.post(url, {'next': evil})
            self.assertRedirects(response, reverse('notifications'), fetch_redirect_response=False)
        response = self.client.post(url, {'next': '/historico/'})
        self.assertRedirects(response, '/historico/', fetch_redirect_response=False)

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


class MarkInitialNotificationsReadCommandTests(TestCase):
    """Story 2.15: backfill de rollout inicial -- marca notificacoes existentes como lidas, sem
    apagar nada, sem afetar notificacoes futuras."""

    def setUp(self):
        self.user = User.objects.create_user(email='backfill@example.com', password='SenhaForte123')

    def _create_notification(self, contest, is_read=False, won=False):
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest=contest,
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        return HitNotification.objects.create(bet=bet, won=won, is_read=is_read)

    def test_dry_run_does_not_change_anything(self):
        notification = self._create_notification('9300')
        call_command('mark_initial_notifications_read')
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_apply_marks_unread_notifications_as_read(self):
        notification = self._create_notification('9301')
        call_command('mark_initial_notifications_read', '--apply')
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_apply_never_deletes_anything(self):
        self._create_notification('9302')
        call_command('mark_initial_notifications_read', '--apply')
        self.assertEqual(HitNotification.objects.count(), 1)
        self.assertEqual(GeneratedBet.objects.count(), 1)

    def test_apply_leaves_already_read_notifications_untouched(self):
        already_read = self._create_notification('9303', is_read=True)
        call_command('mark_initial_notifications_read', '--apply')
        already_read.refresh_from_db()
        self.assertTrue(already_read.is_read)

    def test_does_not_affect_notification_created_after_it_ran(self):
        """Sendo uma acao manual pontual (nunca chamada pelo cron), uma notificacao genuina criada
        DEPOIS do backfill nao e afetada -- ela simplesmente nao existia no momento da chamada."""
        call_command('mark_initial_notifications_read', '--apply')
        later_notification = self._create_notification('9304')
        self.assertFalse(later_notification.is_read)

    def test_apply_never_touches_lottery_result(self):
        LotteryResult.objects.create(game='Quina', contest='9305', numbers=[1, 2, 3, 4, 5], clovers=[], prizes={})
        self._create_notification('9305')
        call_command('mark_initial_notifications_read', '--apply')
        self.assertEqual(LotteryResult.objects.count(), 1)

    def test_dry_run_message_and_apply_count_reflect_only_unread_in_mixed_batch(self):
        """Lote misto (lidas + nao lidas juntas): garante que o filtro/update afeta exatamente o
        subconjunto certo, e que a mensagem impressa (o numero que o operador usa como gate de
        seguranca no runbook) reflete a contagem real de nao lidas, nao o total."""
        self._create_notification('9306', is_read=True)
        self._create_notification('9307', is_read=True)
        self._create_notification('9308')
        self._create_notification('9309')
        self._create_notification('9310')

        dry_run_out = StringIO()
        call_command('mark_initial_notifications_read', stdout=dry_run_out)
        self.assertIn('3 HitNotification', dry_run_out.getvalue())
        self.assertEqual(HitNotification.objects.filter(is_read=True).count(), 2)

        apply_out = StringIO()
        call_command('mark_initial_notifications_read', '--apply', stdout=apply_out)
        self.assertIn('3 HitNotification', apply_out.getvalue())
        self.assertEqual(HitNotification.objects.filter(is_read=True).count(), 5)


@override_settings(OPERATOR_ALERT_EMAIL='boss@example.com')


class NotificationMatchedNumbersTests(TestCase):
    """Retro Epic 2 (F3): numeros batidos reusam calculate_bet_prize (2o sorteio da Dupla-Sena, trevos)."""

    def setUp(self):
        self.user = User.objects.create_user(email='batidos@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    def _notification(self, game, numbers, clovers, result_kwargs):
        bet = GeneratedBet.objects.create(user=self.user, game=game, contest='10', numbers=numbers, clovers=clovers)
        LotteryResult.objects.create(game=game, contest='10', **result_kwargs)
        HitNotification.objects.create(bet=bet, won=True)
        return self.client.get(reverse('notifications')).context['notificacoes'][0]

    def test_dupla_sena_shows_matches_of_second_draw_when_it_pays_more(self):
        n = self._notification('Dupla-Sena', [1, 2, 3, 4, 5, 6], [], {
            'numbers': [50, 51, 52, 53, 54, 55],
            'numbers_second_draw': [1, 2, 3, 4, 5, 6],
            'prizes': {}, 'prizes_second_draw': {'6': {'value': 'R$ 1.000,00'}},
        })
        self.assertEqual(n.matched_numbers, [1, 2, 3, 4, 5, 6])
        self.assertEqual(n.matched_draw, 2)
        self.assertContains(self.client.get(reverse('notifications')), '2º sorteio')

    def test_dupla_sena_first_draw_keeps_first(self):
        n = self._notification('Dupla-Sena', [1, 2, 3, 4, 5, 6], [], {
            'numbers': [1, 2, 3, 4, 5, 6], 'numbers_second_draw': [50, 51, 52, 53, 54, 55],
            'prizes': {'6': {'value': 'R$ 1.000,00'}}, 'prizes_second_draw': {},
        })
        self.assertEqual(n.matched_numbers, [1, 2, 3, 4, 5, 6])
        self.assertEqual(n.matched_draw, 1)

    def test_milionaria_shows_matched_clovers(self):
        n = self._notification('Milionaria', [1, 2, 3, 4, 5, 6], [3, 4], {
            'numbers': [1, 2, 3, 4, 5, 6], 'clovers': [4, 6],
            'prizes': {'6': {'value': 'R$ 5.000,00'}},
        })
        self.assertEqual(n.matched_clovers, [4])
        self.assertContains(self.client.get(reverse('notifications')), 'lq-ball-clover')
