from django.contrib import admin
from .models import GeneratedBet, GameStatistics, HitNotification, NotificationPreference


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
