def theme_context(request):
    """Adiciona informacao de tema ao contexto de todas as views."""
    if request.user.is_authenticated:
        theme = request.user.tema_preferido
    else:
        theme = request.session.get('theme', 'light')

    return {
        'theme': theme,
        'is_dark': theme == 'dark',
    }
