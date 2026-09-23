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

    def test_lotteryresult_admin_list_loads(self):
        response = self.client.get('/admin/loterias_core/lotteryresult/')
        self.assertEqual(response.status_code, 200)

    def test_generatedbet_admin_normalizes_leading_zero_contest(self):
        """Story 2.16: admin normaliza Concurso igual as views publicas (Story 2.12)."""
        target_user = User.objects.create_user(email='betadmin@example.com', password='SenhaForte123')
        response = self.client.post('/admin/loterias_core/generatedbet/add/', {
            'user': target_user.pk,
            'game': 'Mega-sena',
            'contest': '02500',
            'numbers': '[1, 2, 3, 4, 5, 6]',
            'clovers': '[]',
            'manual': False,
            'result_checked': False,
            'hits': 0,
            'prize': '0',
            'prize_description': '',
        })
        self.assertEqual(response.status_code, 302)
        bet = GeneratedBet.objects.get(user=target_user)
        self.assertEqual(bet.contest, '2500')

    def test_generatedbet_admin_rejects_non_numeric_contest(self):
        target_user = User.objects.create_user(email='betadmin2@example.com', password='SenhaForte123')
        response = self.client.post('/admin/loterias_core/generatedbet/add/', {
            'user': target_user.pk,
            'game': 'Mega-sena',
            'contest': 'ESPECIAL-2026',
            'numbers': '[1, 2, 3, 4, 5, 6]',
            'clovers': '[]',
            'manual': False,
            'result_checked': False,
            'hits': 0,
            'prize': '0',
            'prize_description': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Numero de concurso invalido')
        self.assertFalse(GeneratedBet.objects.filter(user=target_user).exists())

    def test_lotteryresult_admin_normalizes_leading_zero_contest(self):
        response = self.client.post('/admin/loterias_core/lotteryresult/add/', {
            'game': 'Mega-sena',
            'contest': '03500',
            'numbers': '[1, 2, 3, 4, 5, 6]',
            'clovers': '[]',
            'prizes': '{}',
            'source': 'CEF',
        })
        self.assertEqual(response.status_code, 302)
        result = LotteryResult.objects.get(game='Mega-sena')
        self.assertEqual(result.contest, '3500')

    def test_lotteryresult_admin_rejects_non_numeric_contest(self):
        response = self.client.post('/admin/loterias_core/lotteryresult/add/', {
            'game': 'Mega-sena',
            'contest': 'ESPECIAL-2026',
            'numbers': '[1, 2, 3, 4, 5, 6]',
            'clovers': '[]',
            'prizes': '{}',
            'source': 'CEF',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Numero de concurso invalido')
        self.assertFalse(LotteryResult.objects.filter(game='Mega-sena').exists())

    def test_generatedbet_admin_normalizes_leading_zero_contest_on_edit(self):
        """Story 2.16: a normalizacao tambem vale ao EDITAR um registro existente, nao so ao criar
        -- o relato original do bug era especificamente sobre edicao direta pelo admin."""
        target_user = User.objects.create_user(email='betadmin3@example.com', password='SenhaForte123')
        bet = GeneratedBet.objects.create(
            user=target_user, game='Mega-sena', contest='4000',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        response = self.client.post(f'/admin/loterias_core/generatedbet/{bet.pk}/change/', {
            'user': target_user.pk,
            'game': 'Mega-sena',
            'contest': '04001',
            'numbers': '[7, 8, 9, 10, 11, 12]',
            'clovers': '[]',
            'manual': False,
            'result_checked': False,
            'hits': 0,
            'prize': '0',
            'prize_description': '',
        })
        self.assertEqual(response.status_code, 302)
        bet.refresh_from_db()
        self.assertEqual(bet.contest, '4001')

    def test_lotteryresult_admin_normalization_surfaces_real_duplicate_via_unique_together(self):
        """Story 2.16: prova que a normalizacao realmente fecha o bug original -- depois dela, uma
        segunda grafia ('05000') do MESMO concurso real ja existente ('5000') colide de verdade
        contra unique_together, em vez de criar silenciosamente um 2o registro pro mesmo concurso."""
        LotteryResult.objects.create(game='Mega-sena', contest='5000', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        response = self.client.post('/admin/loterias_core/lotteryresult/add/', {
            'game': 'Mega-sena',
            'contest': '05000',
            'numbers': '[7, 8, 9, 10, 11, 12]',
            'clovers': '[]',
            'prizes': '{}',
            'source': 'CEF',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Resultado Oficial com este Jogo e Concurso já existe')
        self.assertEqual(LotteryResult.objects.filter(game='Mega-sena').count(), 1)

    def test_capturefailurealert_admin_normalizes_leading_zero_contest(self):
        response = self.client.post('/admin/loterias_core/capturefailurealert/add/', {
            'game': 'Mega-sena',
            'contest': '06000',
        })
        self.assertEqual(response.status_code, 302)
        alert = CaptureFailureAlert.objects.get(game='Mega-sena')
        self.assertEqual(alert.contest, '6000')
