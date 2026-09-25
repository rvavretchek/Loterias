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


class NormalizeContestTests(TestCase):
    def test_strips_leading_zeros(self):
        self.assertEqual(normalize_contest('02500'), '2500')

    def test_leaves_already_normalized_value_unchanged(self):
        self.assertEqual(normalize_contest('2500'), '2500')

    def test_strips_whitespace_before_validating(self):
        self.assertEqual(normalize_contest('  2500  '), '2500')

    def test_rejects_non_numeric_value(self):
        with self.assertRaises(ValueError):
            normalize_contest('ESPECIAL-2026')

    def test_rejects_empty_value(self):
        with self.assertRaises(ValueError):
            normalize_contest('   ')

    def test_rejects_negative_looking_value(self):
        with self.assertRaises(ValueError):
            normalize_contest('-2500')


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

    def test_dupla_sena_uses_second_draw_when_its_prize_is_higher(self):
        """Story 2.18: usuario bate so 4 no 1o sorteio (premio menor) mas 6 no 2o (premio maior) --
        calculate_bet_prize usa o de maior premio, nunca o 1o sorteio por padrao."""
        result = {
            'numbers': [1, 2, 3, 4, 50, 60],
            'numbers_second_draw': [10, 20, 30, 40, 50, 60],
            'clovers': [],
            'prizes': {'4': {'value': 'R$ 100,00', 'winners': 500}},
            'prizes_second_draw': {'6': {'value': 'R$ 500.000,00', 'winners': 1}},
        }
        prize = calculate_bet_prize('Dupla-Sena', [10, 20, 30, 40, 50, 60], [], result)
        self.assertEqual(prize['hits'], 6)
        self.assertEqual(prize['value'], 'R$ 500.000,00')
        self.assertTrue(prize['won'])

    def test_dupla_sena_keeps_first_draw_when_it_is_the_better_prize(self):
        """Story 2.18: quando o 1o sorteio rende mais que o 2o, o resultado fica com o 1o (nunca
        troca pra pior, e nunca soma os 2)."""
        result = {
            'numbers': [10, 20, 30, 40, 50, 60],
            'numbers_second_draw': [1, 2, 3, 4, 50, 60],
            'clovers': [],
            'prizes': {'6': {'value': 'R$ 500.000,00', 'winners': 1}},
            'prizes_second_draw': {'4': {'value': 'R$ 100,00', 'winners': 500}},
        }
        prize = calculate_bet_prize('Dupla-Sena', [10, 20, 30, 40, 50, 60], [], result)
        self.assertEqual(prize['hits'], 6)
        self.assertEqual(prize['value'], 'R$ 500.000,00')

    def test_dupla_sena_without_second_draw_data_falls_back_to_first_draw_only(self):
        """Story 2.18: official_result sem numbers_second_draw (dado capturado antes desta story,
        ou 2o sorteio ainda nao publicado) nao quebra -- calculate_bet_prize usa so o 1o sorteio."""
        result = {
            'numbers': [1, 2, 3, 4, 5, 6],
            'clovers': [],
            'prizes': {'6': {'value': 'R$ 500.000,00', 'winners': 1}},
        }
        prize = calculate_bet_prize('Dupla-Sena', [1, 2, 3, 4, 5, 6], [], result)
        self.assertEqual(prize['hits'], 6)
        self.assertEqual(prize['value'], 'R$ 500.000,00')

    def test_dupla_sena_keeps_first_draw_on_tie(self):
        """Story 2.18: quando os 2 sorteios rendem o MESMO valor (aqui, por faixas diferentes que
        coincidem no valor), o 1o sorteio vence por padrao -- comparacao usa `>` estrito, nunca
        `>=`; desempate documentado e testado, nao implicito."""
        result = {
            'numbers': [1, 2, 3, 4, 5, 6],
            'numbers_second_draw': [1, 2, 3, 4, 7, 8],
            'clovers': [],
            'prizes': {'6': {'value': 'R$ 500.000,00', 'winners': 1}},
            'prizes_second_draw': {'4': {'value': 'R$ 500.000,00', 'winners': 1}},
        }
        prize = calculate_bet_prize('Dupla-Sena', [1, 2, 3, 4, 5, 6], [], result)
        self.assertEqual(prize['value'], 'R$ 500.000,00')
        self.assertEqual(prize['hits'], 6)

    def test_non_dupla_sena_game_ignores_second_draw_fields_even_if_present(self):
        """Story 2.18: a comparacao de 2 sorteios e exclusiva da Dupla-Sena -- mesmo que
        numbers_second_draw venha preenchido por engano, outro jogo nunca considera."""
        result = {
            'numbers': [1, 2, 3, 4, 5],
            'numbers_second_draw': [10, 20, 30, 40, 50],
            'clovers': [],
            'prizes': {'5': {'value': 'R$ 1.000,00', 'winners': 1}},
            'prizes_second_draw': {'5': {'value': 'R$ 999.999,00', 'winners': 1}},
        }
        prize = calculate_bet_prize('Quina', [1, 2, 3, 4, 5], [], result)
        self.assertEqual(prize['value'], 'R$ 1.000,00')


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
    def test_dupla_sena_captures_second_draw_numbers_and_prizes(self, mock_get):
        """Story 2.18: com listaDezenasSegundoSorteio presente, os numeros do 2o sorteio sao
        capturados, e a 2a metade de listaRateioPremio (faixas do 2o sorteio) vira prizes_second_draw
        -- separado do prizes (1o sorteio), nunca misturado."""
        self._mock_response(mock_get, {
            'numero': 3007,
            'listaDezenas': ['10', '24', '26', '31', '32', '48'],
            'listaDezenasSegundoSorteio': ['09', '23', '32', '33', '39', '48'],
            'listaRateioPremio': [
                {'descricaoFaixa': '6 acertos', 'faixa': 1, 'numeroDeGanhadores': 0, 'valorPremio': 0.0},
                {'descricaoFaixa': '5 acertos', 'faixa': 2, 'numeroDeGanhadores': 9, 'valorPremio': 7366.49},
                {'descricaoFaixa': '4 acertos', 'faixa': 3, 'numeroDeGanhadores': 595, 'valorPremio': 127.34},
                {'descricaoFaixa': '3 acertos', 'faixa': 4, 'numeroDeGanhadores': 11016, 'valorPremio': 3.43},
                {'descricaoFaixa': '6 acertos', 'faixa': 5, 'numeroDeGanhadores': 0, 'valorPremio': 0.0},
                {'descricaoFaixa': '5 acertos', 'faixa': 6, 'numeroDeGanhadores': 14, 'valorPremio': 4262.04},
                {'descricaoFaixa': '4 acertos', 'faixa': 7, 'numeroDeGanhadores': 714, 'valorPremio': 106.11},
                {'descricaoFaixa': '3 acertos', 'faixa': 8, 'numeroDeGanhadores': 12129, 'valorPremio': 3.12},
            ],
        })
        result = fetch_cef_result('Dupla-Sena', '3007')
        self.assertEqual(result['numbers_second_draw'], [9, 23, 32, 33, 39, 48])
        self.assertEqual(result['prizes']['5']['winners'], 9)
        self.assertEqual(result['prizes_second_draw']['5']['winners'], 14)
        self.assertEqual(result['prizes_second_draw']['5']['value'], 'R$ 4.262,04')

    @patch('apps.loterias_core.utils.requests.get')
    def test_dupla_sena_without_second_draw_field_leaves_it_empty(self, mock_get):
        """Story 2.18: se a API ainda nao publicou listaDezenasSegundoSorteio (ex. captura entre o
        1o e o 2o sorteio do mesmo concurso), numbers_second_draw fica vazio, sem quebrar."""
        self._mock_response(mock_get, {
            'numero': 3008,
            'listaDezenas': ['01', '05', '18', '22', '28', '30'],
            'listaRateioPremio': [
                {'descricaoFaixa': '6 acertos', 'faixa': 1, 'numeroDeGanhadores': 0, 'valorPremio': 0.0},
            ],
        })
        result = fetch_cef_result('Dupla-Sena', '3008')
        self.assertEqual(result['numbers_second_draw'], [])
        self.assertEqual(result['prizes_second_draw'], {})

    @patch('apps.loterias_core.utils.requests.get')
    def test_non_dupla_sena_game_always_has_empty_second_draw_fields(self, mock_get):
        """Story 2.18: os 2 campos de 2o sorteio ficam sempre presentes no dict devolvido, mesmo
        pra jogos que nunca tem 2 sorteios -- chamadores nao precisam checar o jogo antes de ler."""
        self._mock_response(mock_get, {
            'numero': 2500,
            'listaDezenas': ['01', '05', '18', '22', '28', '30'],
            'listaRateioPremio': [],
        })
        result = fetch_cef_result('Mega-sena', '2500')
        self.assertEqual(result['numbers_second_draw'], [])
        self.assertEqual(result['prizes_second_draw'], {})

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

    @patch('apps.loterias_core.utils.requests.get')
    def test_tier_with_positive_value_and_missing_winners_keeps_value_with_winners_none(self, mock_get):
        """Story 2.11: uma faixa premiada (valorPremio > 0) sem numeroDeGanhadores informado
        (chave ausente, None -- nao simplesmente 0) e uma inconsistencia de dado -- winners fica
        None (falha de extracao isolada a esse campo), mas a faixa NAO e descartada por inteiro:
        o value (unico campo que calculate_bet_prize realmente usa) tem que ser preservado,
        senao um premio real seria negado ou subestimado por causa de um campo que nem influencia
        o calculo do premio."""
        self._mock_response(mock_get, {
            'numero': 2500,
            'listaDezenas': ['04', '08', '15', '16', '23', '42'],
            'listaRateioPremio': [
                {'descricaoFaixa': '6 acertos', 'faixa': 1, 'valorPremio': 50000000.0},
            ],
        })
        result = fetch_cef_result('Mega-sena', '2500')
        self.assertEqual(result['prizes']['6']['value'], 'R$ 50.000.000,00')
        self.assertIsNone(result['prizes']['6']['winners'])

    @patch('apps.loterias_core.utils.requests.get')
    def test_tier_with_zero_value_and_missing_winners_is_still_extracted(self, mock_get):
        """Diferente do caso acima: valor zerado (concurso acumulado, sem premio real naquela
        faixa) e um dado legitimo, mesmo sem numeroDeGanhadores explicito -- nao e falha."""
        self._mock_response(mock_get, {
            'numero': 2500,
            'listaDezenas': ['04', '08', '15', '16', '23', '42'],
            'listaRateioPremio': [
                {'descricaoFaixa': '6 acertos', 'faixa': 1, 'valorPremio': 0.0},
            ],
        })
        result = fetch_cef_result('Mega-sena', '2500')
        self.assertEqual(result['prizes']['6'], {'value': 'R$ 0,00', 'winners': 0})

    @patch('apps.loterias_core.utils.requests.get')
    def test_tier_with_explicit_zero_winners_and_positive_value_is_kept_as_is(self, mock_get):
        """Documenta uma decisao de escopo (nao um bug): a Story 2.11 so trata como falha o caso
        de numeroDeGanhadores AUSENTE (None) -- um valor explicito de 0 ganhadores com premio
        positivo (inconsistencia no sentido oposto, ex. erro de digitacao da API) nao e coberto
        por esta story e passa direto, gravado como veio."""
        self._mock_response(mock_get, {
            'numero': 2500,
            'listaDezenas': ['04', '08', '15', '16', '23', '42'],
            'listaRateioPremio': [
                {'descricaoFaixa': '6 acertos', 'faixa': 1, 'numeroDeGanhadores': 0, 'valorPremio': 50000000.0},
            ],
        })
        result = fetch_cef_result('Mega-sena', '2500')
        self.assertEqual(result['prizes']['6'], {'value': 'R$ 50.000.000,00', 'winners': 0})

    @patch('apps.loterias_core.utils.requests.get')
    def test_negative_or_invalid_prize_value_discards_the_tier(self, mock_get):
        """valorPremio negativo ou de tipo invalido (string nao numerica) e dado corrompido --
        descarta a faixa inteira, ao contrario do caso de winners ausente (onde o value ainda e
        confiavel)."""
        self._mock_response(mock_get, {
            'numero': 2500,
            'listaDezenas': ['04', '08', '15', '16', '23', '42'],
            'listaRateioPremio': [
                {'descricaoFaixa': '6 acertos', 'faixa': 1, 'numeroDeGanhadores': 1, 'valorPremio': -100.0},
                {'descricaoFaixa': '5 acertos', 'faixa': 2, 'numeroDeGanhadores': 1, 'valorPremio': 'nao-e-numero'},
            ],
        })
        result = fetch_cef_result('Mega-sena', '2500')
        self.assertEqual(result['prizes'], {})

    @patch('apps.loterias_core.utils.requests.get')
    def test_dupla_sena_first_draw_winners_failure_does_not_get_overwritten_by_second_draw(self, mock_get):
        """Regressao encontrada na revisao: a dedup por hits_key precisa reservar a chave na
        PRIMEIRA ocorrencia mesmo quando winners fica None -- senao a 2a ocorrencia (2o sorteio
        da Dupla-Sena) substituiria silenciosamente a 1a, quebrando 'fica com a primeira
        ocorrencia' (comportamento ja estabelecido desde a Story 2.1)."""
        self._mock_response(mock_get, {
            'numero': 2600,
            'listaDezenas': ['01', '05', '18', '22', '28', '30'],
            'listaRateioPremio': [
                {'descricaoFaixa': '6 acertos', 'faixa': 1, 'valorPremio': 999999.0},
                {'descricaoFaixa': '6 acertos', 'faixa': 5, 'numeroDeGanhadores': 1, 'valorPremio': 111111.0},
            ],
        })
        result = fetch_cef_result('Dupla-Sena', '2600')
        self.assertEqual(result['prizes']['6']['value'], 'R$ 999.999,00')
        self.assertIsNone(result['prizes']['6']['winners'])

    @patch('apps.loterias_core.utils.requests.get')
    def test_extracts_real_value_and_winners_for_multiple_tiers_of_the_same_game(self, mock_get):
        """Story 2.11, AC principal -- teste nominal pra fechar a rastreabilidade epics.md<->codigo,
        ainda que o mecanismo em si (extracao de valor+ganhadores reais por faixa via a API
        oficial) exista desde a Story 2.1 (ver tambem test_matching_contest_returns_result_with_numbers)."""
        self._mock_response(mock_get, {
            'numero': 2500,
            'listaDezenas': ['04', '08', '15', '16', '23', '42'],
            'listaRateioPremio': [
                {'descricaoFaixa': '6 acertos', 'faixa': 1, 'numeroDeGanhadores': 1, 'valorPremio': 50000000.0},
                {'descricaoFaixa': '5 acertos', 'faixa': 2, 'numeroDeGanhadores': 25, 'valorPremio': 40000.0},
                {'descricaoFaixa': '4 acertos', 'faixa': 3, 'numeroDeGanhadores': 5000, 'valorPremio': 900.0},
            ],
        })
        result = fetch_cef_result('Mega-sena', '2500')
        self.assertEqual(result['prizes']['6'], {'value': 'R$ 50.000.000,00', 'winners': 1})
        self.assertEqual(result['prizes']['5'], {'value': 'R$ 40.000,00', 'winners': 25})
        self.assertEqual(result['prizes']['4'], {'value': 'R$ 900,00', 'winners': 5000})

    @patch('apps.loterias_core.utils.requests.get')
    def test_extraction_completely_empty_still_saves_numbers_and_falls_back_to_prizetier(self, mock_get):
        """Story 2.11 AC: se a pagina nao trouxer faixa nenhuma (listaRateioPremio vazio -- caso
        independente do mecanismo novo de winners=None desta story), o resultado ainda e salvo
        com os numeros sorteados, e calculate_bet_prize cai pro PrizeTier vigente -- comportamento
        ja existente desde a Story 2.8/AD-10, confirmado aqui na integracao real com
        fetch_cef_result."""
        self._mock_response(mock_get, {
            'numero': 2500,
            'listaDezenas': ['04', '08', '15', '16', '23', '42'],
            'listaRateioPremio': [],
        })
        result = fetch_cef_result('Mega-sena', '2500')
        self.assertIsNotNone(result)
        self.assertEqual(result['numbers'], [4, 8, 15, 16, 23, 42])
        self.assertEqual(result['prizes'], {})

        PrizeTier.objects.create(
            game='Mega-sena', hits=6, reference_month=timezone.now().date().replace(day=1),
            value=Decimal('50000000.00'), winners=1,
        )
        prize = calculate_bet_prize('Mega-sena', [4, 8, 15, 16, 23, 42], [], result)
        self.assertTrue(prize['won'])
        self.assertEqual(prize['value'], 'R$ 50.000.000,00')

    @patch('apps.loterias_core.utils.requests.get')
    def test_prize_value_traceability_uses_the_real_concurso_value_over_generic_prizetier(self, mock_get):
        """Story 2.11 AC: quando o concurso especifico tem o valor real (ex. jackpot acumulado
        maior que o PrizeTier generico do mes), esse valor tem prioridade. Mecanismo ja existente
        desde a correcao da Story 2.8 (test_concurso_specific_prizes_remain_ground_truth_...) --
        este teste so fecha a rastreabilidade nominal do AC desta story via fetch_cef_result."""
        self._mock_response(mock_get, {
            'numero': 2500,
            'listaDezenas': ['04', '08', '15', '16', '23', '42'],
            'listaRateioPremio': [
                {'descricaoFaixa': '6 acertos', 'faixa': 1, 'numeroDeGanhadores': 1, 'valorPremio': 123456789.0},
            ],
        })
        result = fetch_cef_result('Mega-sena', '2500')
        PrizeTier.objects.create(
            game='Mega-sena', hits=6, reference_month=timezone.now().date().replace(day=1),
            value=Decimal('50000000.00'), winners=1,
        )
        prize = calculate_bet_prize('Mega-sena', [4, 8, 15, 16, 23, 42], [], result)
        self.assertEqual(prize['value'], 'R$ 123.456.789,00')


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
    def test_dupla_sena_second_draw_is_persisted(self, mock_fetch):
        """Story 2.18: fetch_daily_results persiste numbers_second_draw/prizes_second_draw junto
        com o 1o sorteio."""
        GeneratedBet.objects.create(
            user=self.user, game='Dupla-Sena', contest='3007',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        mock_fetch.return_value = {
            'numbers': [10, 24, 26, 31, 32, 48],
            'numbers_second_draw': [9, 23, 32, 33, 39, 48],
            'clovers': [],
            'prizes': {'6': {'value': 'R$ 0,00'}},
            'prizes_second_draw': {'6': {'value': 'R$ 0,00'}},
        }
        fetch_daily_results()
        result = LotteryResult.objects.get(game='Dupla-Sena', contest='3007')
        self.assertEqual(result.numbers_second_draw, [9, 23, 32, 33, 39, 48])
        self.assertEqual(result.prizes_second_draw, {'6': {'value': 'R$ 0,00'}})

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_dupla_sena_without_second_draw_yet_stays_open_for_next_run(self, mock_fetch):
        """Story 2.18: se o 2o sorteio ainda nao veio na captura, o par continua em open_pairs na
        proxima execucao -- nunca fica incompleto pra sempre so porque ja existe um LotteryResult."""
        GeneratedBet.objects.create(
            user=self.user, game='Dupla-Sena', contest='3009',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        mock_fetch.return_value = {
            'numbers': [10, 24, 26, 31, 32, 48],
            'numbers_second_draw': [],
            'clovers': [],
            'prizes': {'6': {'value': 'R$ 0,00'}},
            'prizes_second_draw': {},
        }
        fetch_daily_results()
        self.assertEqual(mock_fetch.call_count, 1)

        mock_fetch.return_value = {
            'numbers': [10, 24, 26, 31, 32, 48],
            'numbers_second_draw': [9, 23, 32, 33, 39, 48],
            'clovers': [],
            'prizes': {'6': {'value': 'R$ 0,00'}},
            'prizes_second_draw': {'6': {'value': 'R$ 0,00'}},
        }
        fetch_daily_results()
        self.assertEqual(mock_fetch.call_count, 2)
        result = LotteryResult.objects.get(game='Dupla-Sena', contest='3009')
        self.assertEqual(result.numbers_second_draw, [9, 23, 32, 33, 39, 48])

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

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_manual_bet_saved_before_capture_is_checked_retroactively_when_it_wins(self, mock_fetch):
        """Story 6.4 (FR-26): palpite manual guardado ANTES do resultado existir e conferido
        certo assim que a captura roda depois -- ponta a ponta, sem nenhuma acao do usuario."""
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='500',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0, manual=True,
        )
        self.assertFalse(LotteryResult.objects.filter(game='Quina', contest='500').exists())
        mock_fetch.return_value = {
            'numbers': [1, 2, 3, 4, 5], 'clovers': [], 'prizes': {'5': {'value': 'R$ 2.000,00'}},
        }
        fetch_daily_results()
        bet.refresh_from_db()
        self.assertTrue(bet.result_checked)
        self.assertEqual(bet.hits, 5)
        self.assertEqual(bet.prize, Decimal('2000.00'))
        notification = HitNotification.objects.get(bet=bet)
        self.assertTrue(notification.won)

    @patch('apps.loterias_core.jobs.fetch_cef_result')
    def test_manual_bet_saved_before_capture_gets_no_false_positive_when_it_loses(self, mock_fetch):
        """Story 6.4 (FR-26): o mesmo cenario, mas o jogo NAO bate -- nunca cria HitNotification."""
        bet = GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='501',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0, manual=True,
        )
        mock_fetch.return_value = {
            'numbers': [50, 51, 52, 53, 54], 'clovers': [], 'prizes': {},
        }
        fetch_daily_results()
        bet.refresh_from_db()
        self.assertTrue(bet.result_checked)
        self.assertEqual(bet.hits, 0)
        self.assertEqual(bet.prize, Decimal('0'))
        self.assertFalse(HitNotification.objects.filter(bet=bet).exists())


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


class LotteryResultPurgeAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email='admin-purge@example.com', password='SenhaForte123'
        )
        self.client.force_login(self.admin_user)
        self.changelist_url = '/admin/loterias_core/lotteryresult/'

    def _create_result(self, game='Quina', contest='1', days_old=0):
        result = LotteryResult.objects.create(
            game=game, contest=contest, numbers=[1, 2, 3, 4, 5], clovers=[], prizes={},
        )
        if days_old:
            LotteryResult.objects.filter(pk=result.pk).update(
                captured_at=timezone.now() - timedelta(days=days_old)
            )
        return result

    def test_action_without_apply_shows_confirmation_and_deletes_nothing(self):
        old = self._create_result(days_old=400)
        response = self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [old.pk],
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="cutoff_date"')
        self.assertContains(response, 'name="action" value="purge_until_date"')
        self.assertTrue(LotteryResult.objects.filter(pk=old.pk).exists())

    def test_full_two_step_browser_flow_actually_purges(self):
        """Reproduz o fluxo real do navegador em 2 requests HTTP separados -- POST1 sem apply
        pra pegar a tela de confirmacao renderizada de verdade, extrai dela os campos ocultos
        (action + _selected_action) exatamente como um navegador leria do HTML, e so entao faz o
        POST2 com esses campos + a data escolhida. Achado empirico da revisao: sem os campos
        ocultos certos no template, esse fluxo real nunca purgava nada (respondia 200 sem erro
        nenhum) -- um teste que manda tudo (action+apply+cutoff_date) num unico POST, como os
        demais desta classe, nao pegava essa quebra."""
        old = self._create_result(days_old=400)
        step1 = self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [old.pk],
        })
        html = step1.content.decode()
        selected_pks = re.findall(r'name="_selected_action" value="([^"]+)"', html)
        self.assertEqual(selected_pks, [str(old.pk)])

        cutoff = timezone.localdate() - timedelta(days=1)
        self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': selected_pks,
            'apply': 'apply',
            'cutoff_date': cutoff.isoformat(),
        })
        self.assertFalse(LotteryResult.objects.filter(pk=old.pk).exists())

    def test_staff_without_delete_permission_cannot_purge(self):
        """A acao precisa exigir permissao de delete -- staff so com view/change nao pode
        disparar uma exclusao em massa."""
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        viewer = User.objects.create_user(
            email='viewer-purge@example.com', password='SenhaForte123', is_staff=True,
        )
        content_type = ContentType.objects.get_for_model(LotteryResult)
        viewer.user_permissions.add(
            Permission.objects.get(codename='view_lotteryresult', content_type=content_type)
        )
        self.client.force_login(viewer)

        old = self._create_result(days_old=400)
        cutoff = timezone.localdate() - timedelta(days=1)
        self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [old.pk],
            'apply': 'apply',
            'cutoff_date': cutoff.isoformat(),
        })
        self.assertTrue(LotteryResult.objects.filter(pk=old.pk).exists())

    def test_cutoff_date_today_or_future_is_rejected(self):
        """Sem teto, uma data de hoje ou futura apagaria resultados recem-capturados junto --
        a validacao do form recusa isso antes de qualquer exclusao acontecer."""
        old = self._create_result(days_old=400)
        response = self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [old.pk],
            'apply': 'apply',
            'cutoff_date': timezone.now().date().isoformat(),
        })
        self.assertContains(response, 'precisa ser anterior a hoje')
        self.assertTrue(LotteryResult.objects.filter(pk=old.pk).exists())

    def test_success_message_reports_the_real_deleted_count(self):
        first = self._create_result(contest='1', days_old=400)
        self._create_result(contest='2', days_old=400)
        cutoff = timezone.localdate() - timedelta(days=1)
        response = self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [first.pk],
            'apply': 'apply',
            'cutoff_date': cutoff.isoformat(),
        }, follow=True)
        self.assertContains(response, '2 resultado(s) oficial(is) purgado(s) com sucesso.')

    def test_purge_deletes_only_results_older_than_cutoff(self):
        old = self._create_result(contest='1', days_old=400)
        recent = self._create_result(contest='2', days_old=0)
        cutoff = (timezone.now() - timedelta(days=200)).date()
        self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [old.pk],
            'apply': 'apply',
            'cutoff_date': cutoff.isoformat(),
        })
        self.assertFalse(LotteryResult.objects.filter(pk=old.pk).exists())
        self.assertTrue(LotteryResult.objects.filter(pk=recent.pk).exists())

    def test_purge_protects_result_with_hit_notification(self):
        """Um LotteryResult com um GeneratedBet (mesmo game+contest) premiado com
        HitNotification nunca e apagado, mesmo mais antigo que a data de corte."""
        user = User.objects.create_user(email='purgeuser@example.com', password='SenhaForte123')
        old = self._create_result(contest='1', days_old=400)
        bet = GeneratedBet.objects.create(
            user=user, game='Quina', contest='1', numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=bet, won=True, is_read=False)
        cutoff = timezone.localdate() - timedelta(days=1)
        self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [old.pk],
            'apply': 'apply',
            'cutoff_date': cutoff.isoformat(),
        })
        self.assertTrue(LotteryResult.objects.filter(pk=old.pk).exists())

    def test_purge_protects_regardless_of_notification_read_status(self):
        user = User.objects.create_user(email='purgeuser2@example.com', password='SenhaForte123')
        old = self._create_result(contest='1', days_old=400)
        bet = GeneratedBet.objects.create(
            user=user, game='Quina', contest='1', numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=bet, won=True, is_read=True)
        cutoff = timezone.localdate() - timedelta(days=1)
        self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [old.pk],
            'apply': 'apply',
            'cutoff_date': cutoff.isoformat(),
        })
        self.assertTrue(LotteryResult.objects.filter(pk=old.pk).exists())

    def test_purge_protects_pair_even_when_only_one_of_several_bets_has_a_notification(self):
        """A protecao e por PAR (game+contest via Exists), nao por bet individual -- um segundo
        GeneratedBet do mesmo par sem notificacao nao enfraquece a protecao do par inteiro."""
        user = User.objects.create_user(email='purgeuser4@example.com', password='SenhaForte123')
        other_user = User.objects.create_user(email='purgeuser5@example.com', password='SenhaForte123')
        old = self._create_result(contest='1', days_old=400)
        winning_bet = GeneratedBet.objects.create(
            user=user, game='Quina', contest='1', numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        HitNotification.objects.create(bet=winning_bet, won=True, is_read=False)
        GeneratedBet.objects.create(
            user=other_user, game='Quina', contest='1', numbers=[6, 7, 8, 9, 10], clovers=[], sequential_pairs=0,
        )
        cutoff = timezone.localdate() - timedelta(days=1)
        self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [old.pk],
            'apply': 'apply',
            'cutoff_date': cutoff.isoformat(),
        })
        self.assertTrue(LotteryResult.objects.filter(pk=old.pk).exists())

    def test_pair_with_no_generatedbet_at_all_is_eligible_for_purge(self):
        old = self._create_result(contest='1', days_old=400)
        cutoff = timezone.localdate() - timedelta(days=1)
        self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [old.pk],
            'apply': 'apply',
            'cutoff_date': cutoff.isoformat(),
        })
        self.assertFalse(LotteryResult.objects.filter(pk=old.pk).exists())

    def test_purge_ignores_selection_and_applies_to_all_eligible_pairs(self):
        """A acao e por data de corte, nao por linha selecionada -- so 1 pk selecionado (pra
        habilitar o botao do admin), mas ambos os resultados elegiveis sao apagados."""
        old1 = self._create_result(game='Quina', contest='1', days_old=400)
        old2 = self._create_result(game='Lotofacil', contest='2', days_old=400)
        cutoff = timezone.localdate() - timedelta(days=1)
        self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [old1.pk],
            'apply': 'apply',
            'cutoff_date': cutoff.isoformat(),
        })
        self.assertFalse(LotteryResult.objects.filter(pk=old1.pk).exists())
        self.assertFalse(LotteryResult.objects.filter(pk=old2.pk).exists())

    def test_purge_does_not_touch_prizetier_or_generatedbet(self):
        user = User.objects.create_user(email='purgeuser3@example.com', password='SenhaForte123')
        old = self._create_result(contest='1', days_old=400)
        bet = GeneratedBet.objects.create(
            user=user, game='Quina', contest='1', numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        tier = PrizeTier.objects.create(
            game='Quina', hits=5, reference_month=timezone.now().date().replace(day=1),
            value=Decimal('1.00'), winners=1,
        )
        cutoff = timezone.localdate() - timedelta(days=1)
        self.client.post(self.changelist_url, {
            'action': 'purge_until_date',
            '_selected_action': [old.pk],
            'apply': 'apply',
            'cutoff_date': cutoff.isoformat(),
        })
        self.assertFalse(LotteryResult.objects.filter(pk=old.pk).exists())
        self.assertTrue(GeneratedBet.objects.filter(pk=bet.pk).exists())
        self.assertTrue(PrizeTier.objects.filter(pk=tier.pk).exists())

    def test_no_purge_happens_without_running_the_action(self):
        """Confirma especificamente que as rotinas de cron (fetch_daily_results,
        update_monthly_prize_values) nunca purgam LotteryResult por conta propria -- nao cobre
        qualquer outro caminho hipotetico, so esses dois."""
        old = self._create_result(days_old=3650)
        update_monthly_prize_values()
        fetch_daily_results()
        self.assertTrue(LotteryResult.objects.filter(pk=old.pk).exists())


class ContestNormalizationOnSaveTests(TestCase):
    """Retro do Epic 2, item 7: contest normalizado em qualquer caminho de escrita (nao so views),
    sem nunca rejeitar valor legado nao-numerico -- ver NormalizesContestOnSave.save()."""

    def test_generatedbet_save_normalizes_leading_zeros(self):
        user = User.objects.create_user(email='norm@example.com', password='SenhaForte123')
        bet = GeneratedBet.objects.create(user=user, game='Mega-sena', contest='02500', numbers=[1, 2, 3, 4, 5, 6], clovers=[])
        self.assertEqual(bet.contest, '2500')

    def test_lotteryresult_and_capturefailurealert_save_normalize_too(self):
        result = LotteryResult.objects.create(game='Mega-sena', contest='00300', numbers=[1, 2, 3, 4, 5, 6], clovers=[], prizes={})
        self.assertEqual(result.contest, '300')
        alert = CaptureFailureAlert.objects.create(game='Mega-sena', contest='00007')
        self.assertEqual(alert.contest, '7')

    def test_legacy_non_numeric_contest_is_tolerated_not_rejected(self):
        user = User.objects.create_user(email='legado@example.com', password='SenhaForte123')
        bet = GeneratedBet.objects.create(user=user, game='Mega-sena', contest='ESPECIAL-2026', numbers=[1, 2, 3, 4, 5, 6], clovers=[])
        self.assertEqual(bet.contest, 'ESPECIAL-2026')


class SaveOfficialResultTests(TestCase):
    """Retro do Epic 2, itens 1 e 7: fonte unica pra gravar LotteryResult, com retry sob corrida."""

    def _result(self, **extra):
        return {'numbers': [1, 2, 3, 4, 5, 6], 'clovers': [], 'prizes': {'6': {'value': 'R$ 1,00'}}, **extra}

    def test_creates_then_updates_the_same_row(self):
        obj, created = LotteryResult.objects.save_official_result('Mega-sena', '9000', self._result())
        self.assertTrue(created)
        obj2, created2 = LotteryResult.objects.save_official_result('Mega-sena', '9000', self._result(source='CEF'))
        self.assertFalse(created2)
        self.assertEqual(obj.pk, obj2.pk)
        self.assertEqual(LotteryResult.objects.filter(game='Mega-sena', contest='9000').count(), 1)

    def test_retries_once_on_integrity_error_from_a_concurrent_writer(self):
        real_update_or_create = LotteryResult.objects.update_or_create
        calls = []

        def flaky(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                LotteryResult.objects.create(game='Quina', contest='9001', numbers=[1, 2, 3, 4, 5], clovers=[])
                raise IntegrityError('unique_together corrida simulada')
            return real_update_or_create(*args, **kwargs)

        with patch.object(LotteryResult.objects, 'update_or_create', side_effect=flaky):
            obj, created = LotteryResult.objects.save_official_result('Quina', '9001', self._result(numbers=[1, 2, 3, 4, 5]))
        self.assertEqual(len(calls), 2)
        self.assertEqual(LotteryResult.objects.filter(game='Quina', contest='9001').count(), 1)
        self.assertEqual(obj.numbers, [1, 2, 3, 4, 5])


class ContestCoverageStory62Tests(TestCase):
    """Story 6.2: completa as 4 categorias de normalize_contest nos pontos de entrada que
    ainda nao tinham -- vazio em save_manual_bet_view, invalido/valido no form do admin, e
    fronteira com string de digitos anormalmente grande (limite embutido do Python pro int())."""

    def test_save_manual_bet_rejects_empty_contest(self):
        user = User.objects.create_user(email='vazio6.2@example.com', password='SenhaForte123')
        self.client.force_login(user)
        response = self.client.post(reverse('save_manual_bet'), {
            'jogo': 'Lotofacil', 'concurso': '', 'numeros': '1,2,3,4,5,6,7,8,9,10,11,12,13,14,15',
        }, follow=True)
        self.assertEqual(GeneratedBet.objects.count(), 0)
        mensagens = [(m.message, m.level_tag) for m in response.context['messages']]
        self.assertIn(('Preencha o jogo, concurso e numeracao do jogo manual.', 'error'), mensagens)

    def test_huge_digit_string_contest_is_rejected_not_a_crash(self):
        """O int() do Python recusa strings de digito gigantes (protecao embutida desde 3.11) --
        normalize_contest repassa isso como ValueError, que as views ja tratam como entrada
        invalida. Trava esse comportamento (nao depende de nenhuma checagem propria no codigo)."""
        with self.assertRaises(ValueError):
            normalize_contest('9' * 5000)
        user = User.objects.create_user(email='gigante6.2@example.com', password='SenhaForte123')
        self.client.force_login(user)
        response = self.client.post(reverse('create_bet'), {'jogo': 'Mega-sena', 'concurso': '9' * 5000}, follow=True)
        self.assertEqual(GeneratedBet.objects.count(), 0)
        self.assertTrue(any(m.level_tag == 'error' for m in response.context['messages']))

    def test_admin_form_rejects_invalid_contest_with_clean_message(self):
        """Story 2.16: _NormalizedContestFormMixin.clean_contest -- nunca exercitado por teste."""
        admin_user = User.objects.create_superuser(email='adminform6.2@example.com', password='SenhaForte123')
        self.client.force_login(admin_user)
        response = self.client.post('/admin/loterias_core/lotteryresult/add/', {
            'game': 'Mega-sena', 'contest': 'ESPECIAL-2026', 'numbers': '[]', 'clovers': '[]',
            'prizes': '{}', 'numbers_second_draw': '[]', 'prizes_second_draw': '{}', 'source': 'CEF',
        })
        self.assertEqual(response.status_code, 200)  # re-renderiza o form com erro, nao redireciona
        self.assertContains(response, 'Numero de concurso invalido')
        self.assertFalse(LotteryResult.objects.exists())

    def test_admin_form_normalizes_valid_contest_with_leading_zeros(self):
        admin_user = User.objects.create_superuser(email='adminform6.2b@example.com', password='SenhaForte123')
        self.client.force_login(admin_user)
        response = self.client.post('/admin/loterias_core/lotteryresult/add/', {
            'game': 'Mega-sena', 'contest': '03500', 'numbers': '[1,2,3,4,5,6]', 'clovers': '[]',
            'prizes': '{}', 'numbers_second_draw': '[]', 'prizes_second_draw': '{}', 'source': 'CEF',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(LotteryResult.objects.filter(game='Mega-sena', contest='3500').exists())
