from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse


class RequireCompleteAccountMiddleware:
    """Story 3.5: exige nome/sobrenome (profile_completed=True) antes de qualquer tela, pro
    primeiro login apos a Story 3.3. Nunca pega staff/superuser nem /admin/, e nunca pega quem
    ja existia antes desta feature (profile_completed=True via migration de dados).

    EXEMPT_URL_NAMES cobre rotas utilitarias renderizadas no layout global (base.html) que
    precisam continuar funcionando mesmo com o perfil incompleto -- descoberto empiricamente na
    revisao que toggle_theme (form no cabecalho, presente em toda pagina, inclusive a propria
    tela de completar perfil) ficava mudo sem estar aqui: o clique so redirecionava de volta pra
    complete_profile, sem alternar o tema e sem nenhum sinal de erro."""

    EXEMPT_PATH_PREFIXES = ('/admin/', '/static/', '/media/')
    EXEMPT_URL_NAMES = ('complete_profile', 'account_logout', 'toggle_theme')

    def __init__(self, get_response):
        self.get_response = get_response
        self._exempt_paths = None

    def _get_exempt_paths(self):
        if self._exempt_paths is None:
            self._exempt_paths = {reverse(name) for name in self.EXEMPT_URL_NAMES}
        return self._exempt_paths

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if (
            user is not None
            and user.is_authenticated
            and not user.is_staff
            and not user.is_superuser
            and not user.profile_completed
            and not request.path.startswith(self.EXEMPT_PATH_PREFIXES)
            and request.path not in self._get_exempt_paths()
        ):
            complete_profile_url = reverse('complete_profile')
            query = urlencode({'next': request.get_full_path()})
            return redirect(f'{complete_profile_url}?{query}')
        return self.get_response(request)
