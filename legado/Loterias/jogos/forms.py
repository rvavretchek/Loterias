from django import forms
from .models import TipoJogo


class NovoJogoForm(forms.Form):
    """Formulário para gerar um novo jogo."""

    tipo_jogo = forms.ModelChoiceField(
        queryset=TipoJogo.objects.all(),
        label='Tipo de Jogo',
        empty_label='Selecione...',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_tipo_jogo'}),
    )
    numero_concurso = forms.IntegerField(
        label='Número do Concurso',
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ex: 2750',
            'id': 'id_numero_concurso',
        }),
    )


class CadastrarResultadoForm(forms.Form):
    """Formulário para cadastro manual de resultado oficial."""

    tipo_jogo = forms.ModelChoiceField(
        queryset=TipoJogo.objects.all(),
        label='Tipo de Jogo',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    numero_concurso = forms.IntegerField(
        label='Número do Concurso',
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Ex: 2750',
        }),
    )
    data_sorteio = forms.DateField(
        label='Data do Sorteio',
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'date',
        }),
    )
    dezenas = forms.CharField(
        label='Dezenas Sorteadas',
        help_text='Números separados por vírgula. Ex: 01, 15, 23, 34, 45, 59',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '01, 15, 23, 34, 45, 59',
        }),
    )
    dezenas_segundo_sorteio = forms.CharField(
        label='Dezenas 2º Sorteio (Dupla-Sena)',
        required=False,
        help_text='Preencher apenas para Dupla-Sena',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '09, 17, 18, 21, 22, 39',
        }),
    )
    trevos = forms.CharField(
        label='Trevos (Milionária)',
        required=False,
        help_text='Preencher apenas para +Milionária',
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '3, 5',
        }),
    )

    def _parse_numeros(self, campo):
        """Converte string '01, 15, 23' em lista de inteiros [1, 15, 23]."""
        valor = self.cleaned_data.get(campo, '').strip()
        if not valor:
            return []
        try:
            return sorted([int(n.strip()) for n in valor.split(',') if n.strip()])
        except ValueError:
            raise forms.ValidationError(
                f'Formato inválido em {campo}. Use números separados por vírgula.'
            )

    def clean_dezenas(self):
        return self._parse_numeros('dezenas')

    def clean_dezenas_segundo_sorteio(self):
        return self._parse_numeros('dezenas_segundo_sorteio')

    def clean_trevos(self):
        return self._parse_numeros('trevos')
