from django.db.models import Count, Q

from .models import HitNotification, NotificationPreference


def theme_context(request):
    """Adiciona informacao de tema ao contexto de todas as views."""
    if request.user.is_authenticated:
        theme = request.user.preferred_theme
    else:
        theme = request.session.get('theme', 'light')

    return {
        'theme': theme,
        'is_dark': theme == 'dark',
    }


def notifications_context(request):
    """Adiciona a contagem de notificacoes de acerto nao lidas ao contexto de todas as views --
    zerada se o usuario desativou o aviso no site (Story 2.6). Falha soft (conta zerada) em vez
    de propagar erro -- este processor roda em toda pagina autenticada, entao uma excecao aqui
    derrubaria o site inteiro, nao so o badge."""
    default = {'unread_notifications_count': 0, 'has_unread_won_notification': False}
    if not request.user.is_authenticated:
        return default

    try:
        preference = NotificationPreference.objects.filter(user=request.user).first()
        if preference is not None and not preference.site_enabled:
            return default

        counts = HitNotification.objects.filter(bet__user=request.user, is_read=False).aggregate(
            total=Count('id'),
            won=Count('id', filter=Q(won=True)),
        )
        return {
            'unread_notifications_count': counts['total'] or 0,
            'has_unread_won_notification': bool(counts['won']),
        }
    except Exception:
        return default
