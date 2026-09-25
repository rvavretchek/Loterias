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


class HistoryFiltersTests(TestCase):
    """Story 4.8 (FR-24): filtros cumulativos por querystring."""

    def setUp(self):
        self.user = User.objects.create_user(email='filtros@example.com', password='SenhaForte123')
        self.client.force_login(self.user)
        self.mega = self._bet('Mega-sena', '1', prize=0, when=datetime(2026, 9, 10, 12, 0, tzinfo=dt_timezone.utc))
        self.loto_win = self._bet('Lotomania', '2', prize=Decimal('50'), when=datetime(2026, 9, 15, 12, 0, tzinfo=dt_timezone.utc))
        self.mega_win = self._bet('Mega-sena', '3', prize=Decimal('10'), when=datetime(2026, 9, 20, 12, 0, tzinfo=dt_timezone.utc))

    def _bet(self, game, contest, prize, when):
        bet = GeneratedBet.objects.create(
            user=self.user, game=game, contest=contest, numbers=[1, 2, 3, 4, 5, 6], clovers=[], prize=prize,
        )
        GeneratedBet.objects.filter(pk=bet.pk).update(created_at=when)
        return bet

    def _contests(self, **params):
        response = self.client.get(reverse('history'), params)
        self.assertEqual(response.status_code, 200)
        return sorted(b.contest for b in response.context['jogos']), response

    def test_no_filters_lists_everything(self):
        self.assertEqual(self._contests()[0], ['1', '2', '3'])

    def test_filters_by_game_winners_and_period(self):
        self.assertEqual(self._contests(jogo='Mega-sena')[0], ['1', '3'])
        self.assertEqual(self._contests(premiado='1')[0], ['2', '3'])
        self.assertEqual(self._contests(de='2026-09-15', ate='2026-09-15')[0], ['2'])

    def test_filters_are_cumulative(self):
        self.assertEqual(self._contests(jogo='Mega-sena', premiado='1')[0], ['3'])
        self.assertEqual(self._contests(jogo='Mega-sena', premiado='1', de='2026-09-01', ate='2026-09-12')[0], [])

    def test_period_uses_project_timezone_day_boundaries(self):
        late = self._bet('Quina', '9', prize=0, when=datetime(2026, 9, 25, 2, 30, tzinfo=dt_timezone.utc))  # 24/09 23:30 em Sao Paulo
        self.assertIn('9', self._contests(de='2026-09-24', ate='2026-09-24')[0])
        self.assertNotIn('9', self._contests(de='2026-09-25', ate='2026-09-25')[0])
        self.assertTrue(late.pk)

    def test_contest_ordering_is_numeric_like_and_stable(self):
        self._bet('Quina', '300', prize=0, when=datetime(2026, 9, 1, 12, 0, tzinfo=dt_timezone.utc))
        self._bet('Quina', '2500', prize=0, when=datetime(2026, 9, 1, 12, 0, tzinfo=dt_timezone.utc))
        response = self.client.get(reverse('history'), {'ordenacao': 'contest'})
        contests = [b.contest for b in response.context['jogos']]
        self.assertEqual(contests, ['1', '2', '3', '300', '2500'])

    def test_invalid_values_are_ignored(self):
        contests, response = self._contests(jogo='Xpto', de='ontem', ate='31/12/2026')
        self.assertEqual(contests, ['1', '2', '3'])
        self.assertFalse(response.context['tem_filtros'])

    def test_badges_remove_one_filter_and_keep_the_rest(self):
        _, response = self._contests(jogo='Mega-sena', premiado='1')
        html = response.content.decode()
        self.assertIn('aria-label="Remover filtro Jogo: Mega-sena"', html)
        self.assertIn('aria-label="Remover filtro Só premiados"', html)
        removals = {f['label']: f['remove_qs'] for f in response.context['filtros_ativos']}
        self.assertEqual(removals['Jogo: Mega-sena'], 'premiado=1')
        self.assertEqual(removals['Só premiados'], 'jogo=Mega-sena')

    def test_empty_result_names_filters_and_offers_clear(self):
        _, response = self._contests(jogo='Quina', premiado='1')
        self.assertContains(response, 'Jogo: Quina')
        self.assertContains(response, 'Limpar filtros')

    def test_filter_bar_always_visible_and_pagination_keeps_filters(self):
        for i in range(25):
            self._bet('Quina', str(100 + i), prize=Decimal('1'), when=datetime(2026, 9, 21, 12, 0, tzinfo=dt_timezone.utc))
        response = self.client.get(reverse('history'), {'jogo': 'Quina', 'premiado': '1'})
        self.assertContains(response, 'id="filtros-heading"')
        self.assertContains(response, 'page=2&jogo=Quina&amp;premiado=1')

    def test_dupla_sena_renders_two_labeled_groups_and_many_numbers_wrap(self):
        GeneratedBet.objects.create(user=self.user, game='Dupla-Sena', contest='7', numbers=[1, 2, 3, 4, 5, 6], clovers=[])
        GeneratedBet.objects.create(user=self.user, game='Lotomania', contest='8', numbers=list(range(1, 51)), clovers=[])
        response = self.client.get(reverse('history'))
        self.assertContains(response, '1º sorteio:')
        self.assertContains(response, 'aria-label="2º sorteio"')
        self.assertContains(response, 'role="list"')
        self.assertContains(response, 'lq-balls')


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

    def test_first_time_user_sees_onboarding_guide(self):
        """Story 7.1 (FR-29): quem nunca gerou jogo ve o guia de 3 passos."""
        user = User.objects.create_user(email='primeiravez@example.com', password='SenhaForte123')
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'id="guia-primeiros-passos"')
        self.assertContains(response, 'Gerar jogo')

    def test_returning_user_does_not_see_onboarding_guide(self):
        """Story 7.1 (UX-DR10): quem ja gerou jogo antes nao ve o guia de novo."""
        user = User.objects.create_user(email='veterano@example.com', password='SenhaForte123')
        GeneratedBet.objects.create(
            user=user, game='Mega-sena', contest='1',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'id="guia-primeiros-passos"')

    def test_home_context_exposes_suggested_contests_rendered_in_html(self):
        user = User.objects.create_user(email='sugestao@example.com', password='SenhaForte123')
        LotteryResult.objects.create(game='Mega-sena', contest='2500', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['concursos_sugeridos']['Mega-sena'], '2501')
        self.assertContains(response, 'id="concursos-sugeridos-data"')
        self.assertContains(response, '"Mega-sena": "2501"')

    def test_authenticated_home_puts_selected_game_area_before_selector_and_summary_aside(self):
        """Story 4.1 (FR-16): area 'jogo selecionado' no topo, seletor abaixo, resumo em sidebar."""
        user = User.objects.create_user(email='layout@example.com', password='SenhaForte123')
        self.client.force_login(user)
        html = self.client.get(reverse('home')).content.decode()
        selected_area = html.index('id="jogo-selecionado"')
        selector = html.index('id="seletor-de-jogos"')
        summary_aside = html.index('id="resumo-lateral"')
        self.assertLess(selected_area, selector)
        self.assertLess(selector, summary_aside)
        self.assertRegex(html, r'<aside[^>]*id="resumo-lateral"')
        self.assertRegex(html, r'min-width:\s*1280px')

    def test_authenticated_home_generate_form_wraps_contest_radios_and_submit(self):
        """Story 4.1: a area 'jogo selecionado' e o seletor continuam num unico <form> de geracao."""
        user = User.objects.create_user(email='form@example.com', password='SenhaForte123')
        self.client.force_login(user)
        html = self.client.get(reverse('home')).content.decode()
        form_start = html.index('action="%s"' % reverse('create_bet'))
        form_end = html.index('</form>', form_start)
        form_html = html[form_start:form_end]
        self.assertIn('id="concurso"', form_html)
        self.assertIn('type="submit"', form_html)
        self.assertEqual(form_html.count('name="jogo"'), len(GAMES_CONFIG))
        self.assertLess(form_html.index('id="jogo-selecionado"'), form_html.index('id="seletor-de-jogos"'))

    def test_game_selector_uses_distinct_decorative_icon_per_game(self):
        """Story 4.2 (FR-17/UX-DR1): 1 icone distinto por Jogo, aria-hidden, sem o bi-dice-5 generico."""
        user = User.objects.create_user(email='icones@example.com', password='SenhaForte123')
        self.client.force_login(user)
        html = self.client.get(reverse('home')).content.decode()
        expected = {
            'Mega-sena': 'emoji_events', 'Milionaria': 'local_florist', 'Lotomania': 'pin',
            'Lotofacil': 'bolt', 'Quina': 'star', 'Dupla-Sena': 'filter_2',
        }
        self.assertEqual(set(expected), set(GAMES_CONFIG))
        selector = html[html.index('id="seletor-de-jogos"'):html.index('</form>', html.index('id="seletor-de-jogos"'))]
        for game, icon in expected.items():
            card = selector[selector.index('for="jogo-%s"' % game):]
            card = card[:card.index('</label>')]
            self.assertRegex(card, r'<span class="ms game-icon" aria-hidden="true">%s</span>' % icon)
        self.assertNotIn('>casino<', selector)
        self.assertEqual(len(set(expected.values())), len(expected))

    def test_game_selector_is_keyboard_accessible_radio_pattern_with_non_color_check(self):
        """Story 4.2 (UX-DR7): radios .lq-tile-input + label (sem div onclick), check no card selecionado."""
        user = User.objects.create_user(email='btncheck@example.com', password='SenhaForte123')
        self.client.force_login(user)
        html = self.client.get(reverse('home')).content.decode()
        self.assertNotIn('onclick="selectGame', html)
        for game in GAMES_CONFIG:
            self.assertRegex(html, r'<input type="radio" class="lq-tile-input" name="jogo" id="jogo-%s"' % game)
            self.assertIn('for="jogo-%s"' % game, html)
        self.assertEqual(html.count('game-selector-check" aria-hidden="true"'), len(GAMES_CONFIG))
        self.assertRegex(html, r'\.lq-tile-input:checked \+ \.lq-tile \.game-selector-check\s*\{\s*display:\s*block')

    def test_only_one_edit_rules_link_and_it_comes_after_the_whole_radio_group(self):
        """Regressao (Boss, 2026-09-22): um <a> entre radios do mesmo grupo tira o foco do Tab
        do grupo assim que o 1o radio recebe foco (radios nao-marcados saem da sequencia de Tab
        inteiramente) -- so ha 1 link de editar regras, depois de todos os radios/labels."""
        user = User.objects.create_user(email='tabfix@example.com', password='SenhaForte123')
        self.client.force_login(user)
        html = self.client.get(reverse('home')).content.decode()
        self.assertEqual(html.count('id="jogo-regras-link"'), 1)
        selector = html[html.index('id="seletor-de-jogos"'):html.index('</form>', html.index('id="seletor-de-jogos"'))]
        last_radio = max(selector.index('id="jogo-%s"' % game) for game in GAMES_CONFIG)
        last_label_close = selector.rindex('</label>')
        link_pos = selector.index('id="jogo-regras-link"')
        self.assertGreater(link_pos, last_radio)
        self.assertGreater(link_pos, last_label_close)
        for game in GAMES_CONFIG:
            self.assertIn('data-regras-url="%s"' % reverse('generation_rules', kwargs={'jogo': game.lower()}), selector)

    def test_selected_game_area_is_polite_atomic_live_region(self):
        """Story 4.2 (UX-DR4): area 'jogo selecionado' anunciavel por leitor de tela."""
        user = User.objects.create_user(email='live@example.com', password='SenhaForte123')
        self.client.force_login(user)
        html = self.client.get(reverse('home')).content.decode()
        self.assertRegex(html, r'id="jogo-selecionado-info"[^>]*aria-live="polite"[^>]*aria-atomic="true"')
        self.assertIn('id="jogo-selecionado-atual"', html)
        self.assertIn('data-name="Mega-sena"', html)

    def test_authenticated_home_skips_visitor_hero(self):
        user = User.objects.create_user(email='hero@example.com', password='SenhaForte123')
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'Gere apostas inteligentes')
        self.assertNotContains(response, 'Criar Conta Gratis')

    def test_authenticated_home_keeps_contest_field_and_summary_content(self):
        user = User.objects.create_user(email='conteudo@example.com', password='SenhaForte123')
        GeneratedBet.objects.create(
            user=user, game='Quina', contest='1',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'id="concurso"')
        self.assertContains(response, 'name="concurso"')
        self.assertContains(response, 'Selecione um jogo abaixo')
        for label in ('Jogos guardados', 'Tipos de jogo', 'Jogos recentes'):
            self.assertContains(response, label)
        self.assertEqual(response.context['total_jogos'], 1)

    def test_visitor_home_has_no_summary_sidebar_or_selected_game_area(self):
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'id="resumo-lateral"')
        self.assertNotContains(response, 'id="jogo-selecionado"')
        self.assertTemplateUsed(response, 'loterias_core/landing.html')
        self.assertContains(response, 'Gere com regra, guarde tudo, confira sozinho')
        self.assertContains(response, 'Gerar meu primeiro jogo')
        self.assertContains(response, reverse('account_signup'))
        self.assertContains(response, 'jogadora.jpg')
        self.assertNotContains(response, 'Multitenant')
        self.assertNotContains(response, 'aumente suas chances')
        for game in ('Mega-sena', 'Lotofacil', 'Dupla-Sena'):
            self.assertContains(response, game)

    def test_logged_user_home_is_not_the_landing(self):
        user = User.objects.create_user(email='logado@example.com', password='SenhaForte123')
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertTemplateNotUsed(response, 'loterias_core/landing.html')


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

    def test_bet_detail_marks_hit_and_miss_numbers_when_result_known(self):
        """Retro do Epic 5, item 18: numero a numero (acerto/erro), reusando lq-ball-hit/-not-hit."""
        user = User.objects.create_user(email='acertoerro@example.com', password='SenhaForte123')
        self.client.force_login(user)
        bet = GeneratedBet.objects.create(
            user=user, game='Quina', contest='6001',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Quina', contest='6001', numbers=[1, 2, 60, 61, 62], clovers=[], prizes={},
        )
        response = self.client.get(reverse('bet_detail', args=[bet.pk]))
        html = response.content.decode()
        self.assertContains(response, 'lq-ball-hit', count=2)
        self.assertContains(response, 'lq-ball-not-hit', count=3)
        hit_numbers = re.findall(r'lq-ball-hit"[^>]*>\s*(\d{2})\s*<', html)
        self.assertEqual(sorted(hit_numbers), ['01', '02'])

    def test_bet_detail_shows_plain_balls_without_official_result(self):
        user = User.objects.create_user(email='semresultado@example.com', password='SenhaForte123')
        self.client.force_login(user)
        bet = GeneratedBet.objects.create(
            user=user, game='Quina', contest='6002',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        response = self.client.get(reverse('bet_detail', args=[bet.pk]))
        self.assertNotContains(response, 'lq-ball-hit')
        self.assertNotContains(response, 'lq-ball-not-hit')

    def test_bet_detail_notes_second_draw_when_it_is_the_one_that_paid(self):
        user = User.objects.create_user(email='segundosorteio@example.com', password='SenhaForte123')
        self.client.force_login(user)
        bet = GeneratedBet.objects.create(
            user=user, game='Dupla-Sena', contest='6003',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        LotteryResult.objects.create(
            game='Dupla-Sena', contest='6003',
            numbers=[50, 51, 52, 53, 54, 55], numbers_second_draw=[1, 2, 3, 4, 5, 6],
            prizes={}, prizes_second_draw={'6': {'value': 'R$ 1.000,00'}},
        )
        response = self.client.get(reverse('bet_detail', args=[bet.pk]))
        self.assertContains(response, 'Considerando o 2º sorteio')
        self.assertContains(response, 'lq-ball-hit', count=6)


class LottiqBaseTemplateTests(TestCase):
    """Story 5.1: base com a marca e o CSS do Lottiq Design System."""

    def test_anonymous_header_shows_brand_and_cta(self):
        response = self.client.get(reverse('account_login'))
        self.assertContains(response, '<title>Entrar - Lottiq</title>', html=False)
        self.assertContains(response, 'lottiq-mark.svg')
        self.assertContains(response, 'css/lottiq.css')
        self.assertContains(response, 'Criar conta grátis')
        self.assertNotContains(response, 'Gerador de Loterias')

    def test_logged_user_sees_nav_with_active_item_and_no_old_navbar(self):
        user = User.objects.create_user(email='nav@example.com', password='SenhaForte123')
        self.client.force_login(user)
        response = self.client.get(reverse('history'))
        self.assertContains(response, 'Meus jogos')
        self.assertContains(response, 'aria-current="page"')
        self.assertNotContains(response, 'navbar-brand')

    def test_static_files_exist(self):
        from django.contrib.staticfiles import finders
        for path in ('css/lottiq-tokens.css', 'css/lottiq.css', 'img/lottiq-mark.svg'):
            self.assertIsNotNone(finders.find(path), path)

    def test_ad_zone_is_reserved_on_every_page_outside_the_game_flow(self):
        """Story 7.3 (FR-31/UX-DR12): zona reservada presente, sem integracao real do AdSense."""
        user = User.objects.create_user(email='adzone@example.com', password='SenhaForte123')
        self.client.force_login(user)
        for url_name in ('home', 'history', 'statistics'):
            response = self.client.get(reverse(url_name))
            html = response.content.decode()
            self.assertIn('id="zona-anuncio"', html, url_name)
            self.assertIn('Espaço reservado', html, url_name)
            self.assertNotIn('googlesyndication', html, url_name)
            self.assertNotIn('adsbygoogle', html, url_name)
            # nunca dentro do form de gerar jogo / dos filtros
            if url_name == 'home':
                form_end = html.index('</form>')
                self.assertGreater(html.index('id="zona-anuncio"'), form_end)

    def test_html_tag_carries_data_theme_from_context(self):
        """Story 7.4 (FR-32/UX-DR13): data-theme no <html> reflete theme_context, sem FOUC."""
        user = User.objects.create_user(email='themehtml@example.com', password='SenhaForte123')
        user.preferred_theme = 'dark'
        user.save(update_fields=['preferred_theme'])
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, '<html lang="pt-BR" data-theme="dark">')

    def test_theme_toggle_is_present_in_header_and_points_to_toggle_theme(self):
        response = self.client.get(reverse('account_login'))
        self.assertContains(response, reverse('toggle_theme'))
        self.assertContains(response, 'dark_mode')

    def test_theme_toggle_icon_reflects_dark_mode_when_active(self):
        user = User.objects.create_user(email='themeicon@example.com', password='SenhaForte123')
        user.preferred_theme = 'dark'
        user.save(update_fields=['preferred_theme'])
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'light_mode')
        self.assertContains(response, 'Usar tema claro')


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
