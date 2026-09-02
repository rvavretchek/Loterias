from django.test import TestCase

from apps.accounts.models import User
from apps.loterias_core.utils import calcular_premiacao_jogo, normalizar_numeros


class LoteriasCoreUtilsTests(TestCase):
    def test_normalizar_numeros_passa_lista_aceita(self):
        self.assertEqual(normalizar_numeros('1, 2, 3, 4, 5, 6'), [1, 2, 3, 4, 5, 6])
        self.assertEqual(normalizar_numeros([1, 2, 3, 4]), [1, 2, 3, 4])

    def test_calcular_premiacao_jogo_retorna_acertos_e_valor(self):
        resultado = {
            'numeros': [1, 2, 3, 4, 5, 6],
            'trevos': [2],
            'premiacoes': {
                'sena': {'valor': 'R$ 500.000,00'},
                'quina': {'valor': 'R$ 2.000,00'}
            }
        }

        premio = calcular_premiacao_jogo('Mega-sena', [1, 2, 3, 4, 5, 6], [], resultado)

        self.assertTrue(premio['ganhou'])
        self.assertEqual(premio['acertos'], 6)
        self.assertIn('R$', premio['valor'])
