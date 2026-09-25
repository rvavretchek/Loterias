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


class EndToEndBetLifecycleTests(TestCase):
    """Story 6.6: ciclo completo de uma aposta -- registro -> captura -> premio -> notificacao --
    numa unica passagem, tanto pro fluxo automatico quanto pro manual."""

    def setUp(self):
        self.user = User.objects.create_user(email='e2e6.6@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_automatic_bet_full_lifecycle(self, mock_fetch):
        with patch(
            'apps.loterias_core.views.generate_bet_with_relaxation',
            return_value=([1, 2, 3, 4, 5], [], None),
        ):
            response = self.client.post(reverse('create_bet'), {'jogo': 'Quina', 'concurso': '9100'}, follow=True)
        bet = GeneratedBet.objects.get(user=self.user, game='Quina', contest='9100')
        self.assertRedirects(response, reverse('bet_detail', args=[bet.pk]))
        self.assertFalse(bet.result_checked)
        self.assertFalse(HitNotification.objects.filter(bet=bet).exists())

        mock_fetch.return_value = {'numbers': [1, 2, 3, 4, 5], 'clovers': [], 'prizes': {'5': {'value': 'R$ 5.000,00'}}}
        fetch_daily_results()

        bet.refresh_from_db()
        self.assertTrue(bet.result_checked)
        self.assertEqual(bet.hits, 5)
        self.assertEqual(bet.prize, Decimal('5000.00'))
        notification = HitNotification.objects.get(bet=bet)
        self.assertTrue(notification.won)

        detail = self.client.get(reverse('bet_detail', args=[bet.pk]))
        self.assertEqual(detail.context['premio_info']['hits'], 5)

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    @patch('apps.loterias_core.views.fetch_cef_result')
    def test_manual_bet_shows_prize_immediately_but_notification_waits_for_the_scan(self, mock_view_fetch, mock_job_fetch):
        """save_manual_bet_view aplica o premio na hora (AD-12), mas quem cria a HitNotification
        e sempre _notify_covered_bets (AD-4) -- nunca o proprio caminho de escrita do resultado."""
        result = {'numbers': [1, 2, 3, 4, 5], 'clovers': [], 'prizes': {'5': {'value': 'R$ 3.000,00'}}}
        mock_view_fetch.return_value = result
        response = self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Quina', 'concurso': '9101', 'numeros': '1,2,3,4,5',
        }, follow=True)
        bet = GeneratedBet.objects.get(user=self.user, game='Quina', contest='9101')
        self.assertRedirects(response, reverse('bet_detail', args=[bet.pk]))
        bet.refresh_from_db()
        self.assertTrue(bet.result_checked)
        self.assertEqual(bet.hits, 5)
        self.assertEqual(bet.prize, Decimal('3000.00'))
        # O premio ja aparece na tela de detalhe -- mas a notificacao ainda nao existe.
        detail = self.client.get(reverse('bet_detail', args=[bet.pk]))
        self.assertEqual(detail.context['premio_info']['hits'], 5)
        self.assertFalse(HitNotification.objects.filter(bet=bet).exists())

        mock_job_fetch.return_value = result
        fetch_daily_results()

        notification = HitNotification.objects.get(bet=bet)
        self.assertTrue(notification.won)
