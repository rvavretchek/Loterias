from datetime import datetime, time

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef
from django.shortcuts import render
from django.utils import timezone

from .models import (
    CaptureFailureAlert, GeneratedBet, GameStatistics, HitNotification, LotteryResult,
    NotificationPreference, PrizeTier,
)


@admin.register(GeneratedBet)
class GeneratedBetAdmin(admin.ModelAdmin):
    list_display = ('game', 'contest', 'user', 'sequential_pairs', 'created_at')
    list_filter = ('game', 'created_at', 'sequential_pairs')
    search_fields = ('contest', 'user__email', 'user__first_name')
    date_hierarchy = 'created_at'
    readonly_fields = ('sequential_pairs', 'created_at', 'updated_at')


@admin.register(GameStatistics)
class GameStatisticsAdmin(admin.ModelAdmin):
    list_display = ('game', 'user', 'total_bets', 'last_updated')
    list_filter = ('game', 'last_updated')
    search_fields = ('user__email',)


@admin.register(HitNotification)
class HitNotificationAdmin(admin.ModelAdmin):
    list_display = ('bet', 'won', 'is_read', 'created_at')
    list_filter = ('won', 'is_read', 'created_at')
    search_fields = ('bet__user__email',)
    readonly_fields = ('created_at',)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'site_enabled', 'email_enabled')
    list_filter = ('site_enabled', 'email_enabled')
    search_fields = ('user__email',)


@admin.register(PrizeTier)
class PrizeTierAdmin(admin.ModelAdmin):
    list_display = ('game', 'hits', 'value', 'winners', 'reference_month')
    list_filter = ('game', 'reference_month')
    search_fields = ('game',)


@admin.register(CaptureFailureAlert)
class CaptureFailureAlertAdmin(admin.ModelAdmin):
    list_display = ('game', 'contest', 'created_at')
    list_filter = ('game', 'created_at')
    search_fields = ('game', 'contest')
    readonly_fields = ('created_at',)


class PurgeUntilDateForm(forms.Form):
    cutoff_date = forms.DateField(
        label='Purgar resultados capturados antes de',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def clean_cutoff_date(self):
        cutoff_date = self.cleaned_data['cutoff_date']
        if cutoff_date >= timezone.localdate():
            raise ValidationError(
                'A data de corte precisa ser anterior a hoje -- senao a purga tambem apagaria '
                'resultados recem-capturados.'
            )
        return cutoff_date


@admin.register(LotteryResult)
class LotteryResultAdmin(admin.ModelAdmin):
    """Story 2.10: LotteryResult nunca tinha sido registrado no admin ate agora."""
    list_display = ('game', 'contest', 'captured_at', 'source')
    list_filter = ('game', 'source')
    search_fields = ('contest',)
    date_hierarchy = 'captured_at'
    actions = ['purge_until_date']

    @admin.action(
        description=(
            'Purgar resultados capturados antes de uma data (ignora a selecao de linhas -- '
            'avalia TODOS os resultados; protege os que tem Notificacao de Acerto associada)'
        ),
        permissions=['delete'],
    )
    def purge_until_date(self, request, queryset):
        """Acao de 2 passos (mesmo padrao do 'delete selected' nativo do Django): a tela
        intermediaria precisa reembutir `action` + os checkboxes selecionados como campos ocultos
        no form de confirmacao, senao o segundo POST do navegador real nao tem o que
        `changelist_view` precisa pra chamar esta funcao de novo -- ela simplesmente recarrega a
        changelist normal, sem erro nenhum, sem purgar nada (achado empirico da revisao: os
        testes que enviam action+apply no mesmo POST nao pegam essa quebra, so um teste que
        simula os 2 requests HTTP separados de verdade pega)."""
        if 'apply' in request.POST:
            form = PurgeUntilDateForm(request.POST)
            if form.is_valid():
                cutoff_date = form.cleaned_data['cutoff_date']
                cutoff_datetime = timezone.make_aware(datetime.combine(cutoff_date, time.min))

                protected_pairs = GeneratedBet.objects.filter(
                    game=OuterRef('game'), contest=OuterRef('contest'), notification__isnull=False,
                )
                candidates = LotteryResult.objects.filter(captured_at__lt=cutoff_datetime).annotate(
                    is_protected=Exists(protected_pairs)
                ).filter(is_protected=False)

                deleted_count, _ = candidates.delete()
                self.message_user(
                    request,
                    f'{deleted_count} resultado(s) oficial(is) purgado(s) com sucesso.',
                    messages.SUCCESS,
                )
                return None
        else:
            form = PurgeUntilDateForm()

        selected_pks = request.POST.getlist(ACTION_CHECKBOX_NAME)
        return render(
            request,
            'admin/loterias_core/lotteryresult/purge_until_date.html',
            {
                'form': form,
                'title': 'Purgar resultados oficiais antigos',
                'total_count': LotteryResult.objects.count(),
                'opts': self.model._meta,
                'action_checkbox_name': ACTION_CHECKBOX_NAME,
                'selected_pks': selected_pks,
            },
        )
