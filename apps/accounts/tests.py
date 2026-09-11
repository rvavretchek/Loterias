import os
import re

from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.hashers import PepperedArgon2PasswordHasher
from apps.accounts.models import User
from apps.accounts.signals import send_welcome_email
from apps.loterias_core.models import GeneratedBet


class PasswordHasherTests(SimpleTestCase):
    def test_peppered_argon2_hasher_verifies_password(self):
        original_pepper = os.environ.get('PASSWORD_PEPPER')
        os.environ['PASSWORD_PEPPER'] = 'test-pepper-123'
        try:
            hasher = PepperedArgon2PasswordHasher()
            encoded = hasher.encode('SenhaForte!2026', salt='abcdefghijklmnop')
            self.assertTrue(hasher.verify('SenhaForte!2026', encoded))
            self.assertFalse(hasher.verify('SenhaForte!2026x', encoded))
        finally:
            if original_pepper is None:
                os.environ.pop('PASSWORD_PEPPER', None)
            else:
                os.environ['PASSWORD_PEPPER'] = original_pepper

    def test_peppered_argon2_hasher_requires_pepper(self):
        original_pepper = os.environ.get('PASSWORD_PEPPER')
        os.environ.pop('PASSWORD_PEPPER', None)
        try:
            with override_settings(PASSWORD_PEPPER=''):
                hasher = PepperedArgon2PasswordHasher()
                with self.assertRaises(ImproperlyConfigured):
                    hasher.encode('SenhaForte!2026', salt='abcdefghijklmnop')
        finally:
            if original_pepper is not None:
                os.environ['PASSWORD_PEPPER'] = original_pepper

    def test_different_pepper_fails_verification(self):
        os.environ['PASSWORD_PEPPER'] = 'pepper-a'
        try:
            hasher = PepperedArgon2PasswordHasher()
            encoded = hasher.encode('SenhaForte!2026', salt='abcdefghijklmnop')
        finally:
            pass
        os.environ['PASSWORD_PEPPER'] = 'pepper-b'
        try:
            hasher2 = PepperedArgon2PasswordHasher()
            self.assertFalse(hasher2.verify('SenhaForte!2026', encoded))
        finally:
            os.environ.pop('PASSWORD_PEPPER', None)


class UserManagerTests(TestCase):
    """Regressao: sem este manager, create_user() exige 'username' mesmo com
    USERNAME_FIELD = 'email', e createsuperuser/admin quebram (ver docs/diagnostico-projeto.md)."""

    def test_create_user_with_only_email_and_password(self):
        user = User.objects.create_user(
            email='usuario@example.com',
            password='SenhaForte123',
            first_name='Fulano',
            last_name='Silva',
        )
        self.assertEqual(user.email, 'usuario@example.com')
        self.assertTrue(user.check_password('SenhaForte123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='SenhaForte123')

    def test_create_user_normalizes_email_domain(self):
        user = User.objects.create_user(email='usuario@EXAMPLE.COM', password='SenhaForte123')
        self.assertEqual(user.email, 'usuario@example.com')

    def test_create_superuser_sets_flags(self):
        admin = User.objects.create_superuser(email='admin@example.com', password='SenhaForte123')
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)

    def test_create_superuser_rejects_is_staff_false(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(email='admin@example.com', password='SenhaForte123', is_staff=False)

    def test_user_has_no_username_field(self):
        field_names = [f.name for f in User._meta.get_fields()]
        self.assertNotIn('username', field_names)

    def test_create_user_defaults_to_profile_completed(self):
        """'Perfil pendente' (Story 3.5) e um conceito exclusivo do fluxo publico de cadastro
        so-com-email, que nunca passa por este manager -- create_user() (createsuperuser,
        scripts, testes) sempre espera uma conta pronta pra uso."""
        user = User.objects.create_user(email='pronto@example.com', password='SenhaForte123')
        self.assertTrue(user.profile_completed)

    def test_create_user_respects_explicit_profile_completed_false(self):
        user = User.objects.create_user(
            email='pendente3@example.com', password='SenhaForte123', profile_completed=False,
        )
        self.assertFalse(user.profile_completed)


class UserModelTests(TestCase):
    def test_get_full_name_falls_back_to_email(self):
        user = User.objects.create_user(email='semnome@example.com', password='SenhaForte123')
        self.assertEqual(user.get_full_name(), 'semnome@example.com')

    def test_get_full_name_combines_first_and_last(self):
        user = User.objects.create_user(
            email='fulano@example.com', password='SenhaForte123',
            first_name='Fulano', last_name='Silva',
        )
        self.assertEqual(user.get_full_name(), 'Fulano Silva')

    def test_get_initials_from_full_name(self):
        user = User.objects.create_user(
            email='fulano@example.com', password='SenhaForte123',
            first_name='Fulano', last_name='Silva',
        )
        self.assertEqual(user.get_initials(), 'FS')

    def test_get_initials_falls_back_to_email_first_letter(self):
        user = User.objects.create_user(email='zeta@example.com', password='SenhaForte123')
        self.assertEqual(user.get_initials(), 'Z')

    def test_str_returns_email(self):
        user = User.objects.create_user(email='fulano@example.com', password='SenhaForte123')
        self.assertEqual(str(user), 'fulano@example.com')


class WelcomeEmailSignalTests(TestCase):
    def test_welcome_email_sent_on_user_creation(self):
        User.objects.create_user(email='novo@example.com', password='SenhaForte123', first_name='Novo')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('novo@example.com', mail.outbox[0].to)

    def test_welcome_email_not_resent_on_update(self):
        user = User.objects.create_user(email='novo2@example.com', password='SenhaForte123')
        mail.outbox.clear()
        user.bio = 'Atualizando perfil'
        user.save()
        self.assertEqual(len(mail.outbox), 0)

    def test_welcome_email_not_sent_for_pending_account_with_unusable_password(self):
        """Epic 3: uma conta pendente (fluxo de cadastro so-com-email, senha inutilizavel) nao
        pode receber 'sua conta foi criada com sucesso, acesse agora' -- a conta ainda nao pode
        ser acessada."""
        user = User(email='pendente@example.com')
        user.set_unusable_password()
        user.save()
        self.assertEqual(len(mail.outbox), 0)

    def test_welcome_email_sent_explicitly_when_password_is_set(self):
        """O e-mail de boas-vindas de uma conta pendente e disparado explicitamente quando a
        senha e definida pela primeira vez (InitialOrResetPasswordKeyForm.save()), nao no
        post_save de criacao."""
        user = User(email='pendente2@example.com', first_name='Fulano')
        user.set_unusable_password()
        user.save()
        mail.outbox.clear()
        user.set_password('SenhaForte123')
        user.save()
        send_welcome_email(user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('pendente2@example.com', mail.outbox[0].to)


class ProfileViewTests(TestCase):
    """Regressao do rename de related_name 'jogos'->'bets' (GeneratedBet.user):
    a contagem exibida no perfil (user.bets.count) precisa continuar correta."""

    def setUp(self):
        self.user = User.objects.create_user(email='perfil@example.com', password='SenhaForte123')
        self.client.force_login(self.user)

    def test_profile_shows_correct_count_of_generated_bets(self):
        GeneratedBet.objects.create(
            user=self.user, game='Mega-sena', contest='1',
            numbers=[1, 2, 3, 4, 5, 6], clovers=[], sequential_pairs=0,
        )
        GeneratedBet.objects.create(
            user=self.user, game='Quina', contest='1',
            numbers=[1, 2, 3, 4, 5], clovers=[], sequential_pairs=0,
        )
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['user'].bets.count(), 2)
        self.assertContains(response, '2')


class ToggleThemeViewTests(TestCase):
    """Regressao do rename User.tema_preferido->preferred_theme (Story 1.5)."""

    def test_authenticated_user_toggles_from_light_to_dark(self):
        user = User.objects.create_user(email='tema@example.com', password='SenhaForte123')
        self.assertEqual(user.preferred_theme, 'light')
        self.client.force_login(user)

        self.client.get(reverse('toggle_theme'), HTTP_REFERER='/')

        user.refresh_from_db()
        self.assertEqual(user.preferred_theme, 'dark')

    def test_authenticated_user_toggles_from_dark_to_light(self):
        user = User.objects.create_user(email='tema2@example.com', password='SenhaForte123')
        user.preferred_theme = 'dark'
        user.save(update_fields=['preferred_theme'])
        self.client.force_login(user)

        self.client.get(reverse('toggle_theme'), HTTP_REFERER='/')

        user.refresh_from_db()
        self.assertEqual(user.preferred_theme, 'light')

    def test_anonymous_user_uses_session_without_touching_model(self):
        response = self.client.get(reverse('toggle_theme'), HTTP_REFERER='/', follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('theme'), 'dark')


class SignupFlowTests(TestCase):
    """Story 3.1: cadastro so com e-mail."""

    def test_signup_form_has_only_email_field(self):
        response = self.client.get(reverse('account_signup'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['form'].fields.keys()), ['email'])

    def test_signup_creates_pending_account_with_unusable_password(self):
        self.client.post(reverse('account_signup'), {'email': 'pendente@example.com'})
        user = User.objects.get(email='pendente@example.com')
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.profile_completed)

    def test_signup_sends_confirmation_email(self):
        self.client.post(reverse('account_signup'), {'email': 'confirmar@example.com'})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('confirmar@example.com', mail.outbox[0].to[0])

    def test_pending_account_cannot_login(self):
        self.client.post(reverse('account_signup'), {'email': 'semsenha@example.com'})
        logged_in = self.client.login(email='semsenha@example.com', password='qualquer-coisa')
        self.assertFalse(logged_in)

    def test_signup_redirects_to_verification_sent_page(self):
        response = self.client.post(
            reverse('account_signup'), {'email': 'redireciona@example.com'}, follow=True
        )
        self.assertRedirects(response, reverse('account_email_verification_sent'))

    def test_signup_with_existing_email_shows_same_generic_message_without_duplicating(self):
        """Story 3.1, 2o AC: anti-enumeracao -- e-mail ja cadastrado (allauth
        ACCOUNT_PREVENT_ENUMERATION, default True) nunca cria conta duplicada nem revela que a
        conta ja existe pela resposta HTTP. O dono real da conta AINDA recebe um e-mail (allauth
        send_account_already_exists_mail) -- diferente de nao revelar pra quem preencheu o
        formulario, que e o que a tela generica garante."""
        User.objects.create_user(email='jaexiste@example.com', password='SenhaForte123')
        mail.outbox.clear()  # limpa o e-mail de boas-vindas disparado pelo create_user acima
        response = self.client.post(
            reverse('account_signup'), {'email': 'jaexiste@example.com'}, follow=True
        )
        self.assertRedirects(response, reverse('account_email_verification_sent'))
        self.assertEqual(User.objects.filter(email='jaexiste@example.com').count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('jaexiste@example.com', mail.outbox[0].to)

    def test_signup_page_always_shows_the_submitted_email_regardless_of_existing_account(self):
        """Regressao encontrada na revisao: mostrar o e-mail na tela pos-cadastro so quando a
        sessao foi atualizada (o que so acontecia pra contas NOVAS, ja que o adapter recebia
        user=None pro caso de anti-enumeracao) recriava exatamente o oraculo que
        ACCOUNT_PREVENT_ENUMERATION existe pra evitar -- a tela mudava de conteudo dependendo de
        o e-mail ja existir ou nao. Agora a sessao e atualizada incondicionalmente na view,
        antes de saber se a conta ja existia."""
        User.objects.create_user(email='jaexiste2@example.com', password='SenhaForte123')
        response = self.client.post(
            reverse('account_signup'), {'email': 'jaexiste2@example.com'}, follow=True
        )
        self.assertContains(response, 'jaexiste2@example.com')

    def test_signup_session_email_is_not_stale_from_a_previous_attempt(self):
        """Regressao encontrada na revisao: sem atualizar a sessao no caso 'conta ja existe', uma
        tentativa de cadastro anterior (bem-sucedida, e-mail novo) deixava um e-mail antigo
        preso na sessao, mostrado incorretamente numa tentativa seguinte com OUTRO e-mail. O
        follow=True do 1o POST consome a mensagem flash daquela tentativa (que tambem citaria
        'primeiro@example.com'), isolando a asserção pro estado de SESSAO em si, nao pra
        mensagem acumulada de uma pagina nunca renderizada."""
        self.client.post(reverse('account_signup'), {'email': 'primeiro@example.com'}, follow=True)
        User.objects.create_user(email='segundo-ja-existe@example.com', password='SenhaForte123')
        response = self.client.post(
            reverse('account_signup'), {'email': 'segundo-ja-existe@example.com'}, follow=True
        )
        self.assertContains(response, 'segundo-ja-existe@example.com')
        self.assertNotContains(response, 'primeiro@example.com')


class EmailVerificationRedirectTests(TestCase):
    """Story 3.3: redirecionamento apos confirmar o e-mail."""

    def _confirm(self, user):
        email_address = EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
        key = EmailConfirmationHMAC(email_address).key
        return self.client.post(reverse('account_confirm_email', kwargs={'key': key}), follow=False)

    def test_pending_account_redirects_to_password_creation(self):
        user = User(email='pendente4@example.com')
        user.set_unusable_password()
        user.save()
        response = self._confirm(user)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/password/reset/key/', response.url)

    def test_already_active_account_redirects_to_login_with_message(self):
        """assertRedirects() por padrao faz seu PROPRIO GET no destino pra validar o status code
        (fetch_redirect_response=True) -- isso consumiria a mensagem flash antes do GET manual
        abaixo poder le-la, entao desativamos esse fetch interno aqui."""
        user = User.objects.create_user(email='jaativo@example.com', password='SenhaForte123')
        response = self._confirm(user)
        self.assertRedirects(response, reverse('account_login'), fetch_redirect_response=False)
        response_followed = self.client.get(reverse('account_login'))
        self.assertContains(response_followed, 'Cadastro já confirmado')

    def test_already_authenticated_user_confirming_own_secondary_email_is_not_redirected_to_login(self):
        """Regressao encontrada na revisao: get_email_verification_redirect_url tambem e chamado
        quando um usuario JA LOGADO confirma um segundo e-mail (rota nativa /accounts/email/ do
        allauth, sempre ativa) -- sem essa checagem, ele seria deslogado-na-pratica pra tela de
        login com uma mensagem sem sentido ('cadastro ja confirmado'), quando na verdade so
        deveria continuar navegando normalmente (comportamento padrao do allauth)."""
        user = User.objects.create_user(email='logado@example.com', password='SenhaForte123')
        self.client.force_login(user)
        response = self._confirm(user)
        self.assertNotEqual(response.url, reverse('account_login'))


class InitialPasswordCreationTests(TestCase):
    """Story 3.3: definicao de senha via link (reaproveitando PasswordResetFromKeyView)."""

    def _get_key_url(self, user):
        email_address = EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
        self.client.post(reverse('account_confirm_email', kwargs={'key': EmailConfirmationHMAC(email_address).key}))
        from allauth.account.forms import default_token_generator
        from allauth.account.utils import user_pk_to_url_str
        uidb36 = user_pk_to_url_str(user)
        key = default_token_generator.make_token(user)
        return reverse('account_reset_password_from_key', kwargs={'uidb36': uidb36, 'key': key})

    def _open_form(self, url):
        """A view guarda a key na sessao e redireciona pra URL sem a key (protecao contra
        vazamento via Referer) -- reproduz isso como um navegador real faria. Only o segmento
        da KEY vira 'set-password', o uidb36 continua o mesmo."""
        self.client.get(url)
        base, _, last_segment = url.rstrip('/').rpartition('/')
        uidb36 = last_segment.split('-', 1)[0]
        return f'{base}/{uidb36}-set-password/'

    def test_pending_account_form_requires_terms_acceptance(self):
        """Regressao encontrada na revisao: so checar (200, senha ainda inutilizavel) tambem
        passaria se o TOKEN estivesse quebrado (pagina de vinculo invalido tambem retorna 200 e
        nunca define senha) -- checar o erro de validacao especifico no campo terms_accepted
        descarta essa possibilidade."""
        user = User(email='semtemos@example.com')
        user.set_unusable_password()
        user.save()
        url = self._get_key_url(user)
        form_url = self._open_form(url)
        response = self.client.post(form_url, {'password1': 'SenhaForte123', 'password2': 'SenhaForte123'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('terms_accepted', response.context['form'].errors)
        user.refresh_from_db()
        self.assertFalse(user.has_usable_password())

    def test_pending_account_sets_password_and_logs_in_when_terms_accepted(self):
        user = User(email='comtemos@example.com')
        user.set_unusable_password()
        user.save()
        url = self._get_key_url(user)
        form_url = self._open_form(url)
        mail.outbox.clear()
        response = self.client.post(form_url, {
            'password1': 'SenhaForte123', 'password2': 'SenhaForte123', 'terms_accepted': 'on',
        }, follow=True)
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('comtemos@example.com', mail.outbox[0].to)

    def test_already_active_user_reset_form_never_shows_terms_field(self):
        user = User.objects.create_user(email='resetgenuino@example.com', password='SenhaVelha123')
        url = self._get_key_url(user)
        form_url = self._open_form(url)
        response = self.client.get(form_url)
        self.assertNotIn('terms_accepted', response.context['form'].fields)

    def test_admin_invalidated_password_does_not_require_terms_or_send_welcome_email(self):
        """Regressao encontrada na revisao: has_usable_password()==False tambem e verdade pra
        uma conta JA ATIVA cuja senha foi invalidada por outro motivo (ex. um admin chamando
        set_unusable_password() por seguranca) -- essa pessoa nunca deveria ser tratada como
        'criacao inicial' (reaceite de termos, e-mail dizendo 'sua conta foi criada agora')."""
        user = User.objects.create_user(email='desativado@example.com', password='SenhaAntiga123')
        user.last_login = timezone.now()
        user.set_unusable_password()
        user.save()

        url = self._get_key_url(user)
        form_url = self._open_form(url)
        response = self.client.get(form_url)
        self.assertNotIn('terms_accepted', response.context['form'].fields)

        mail.outbox.clear()
        self.client.post(form_url, {'password1': 'SenhaNova123', 'password2': 'SenhaNova123'})
        self.assertEqual(len(mail.outbox), 0)


class ResendConfirmationEmailTests(TestCase):
    """Story 3.2: reenvio limitado. Cooldown de 60s = rate limiter nativo do allauth
    (ACCOUNT_RATE_LIMITS['confirm_email'], uma unica regra); limite de 5/dia = contador proprio
    em ResendConfirmationEmailView, com cache key dedicada (RESEND_DAILY_LIMIT), desacoplado do
    cooldown -- ver comentario em settings/base.py sobre por que as duas regras NAO podem
    compartilhar a mesma acao/cache key do allauth (achado real da revisao: nesse caso o limite
    diario efetivamente nao funciona, cliques dentro do cooldown ainda consomem a cota)."""

    def _clear_rate_limit(self, email):
        from allauth.core import ratelimit
        from django.test import RequestFactory
        ratelimit.clear(RequestFactory().post('/'), action='confirm_email', key=email.lower())

    def test_resend_for_pending_account_sends_a_new_email(self):
        self.client.post(reverse('account_signup'), {'email': 'reenviar@example.com'})
        mail.outbox.clear()
        self._clear_rate_limit('reenviar@example.com')
        self.client.post(reverse('resend_confirmation'), {'email': 'reenviar@example.com'})
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_within_cooldown_of_the_original_signup_email_does_not_send_again(self):
        """Regressao critica: o cooldown de 60s vale a partir de QUALQUER envio da acao
        confirm_email, inclusive o e-mail original do cadastro -- reenviar segundos depois do
        cadastro (sem tempo suficiente ter passado) tem que ser bloqueado."""
        self.client.post(reverse('account_signup'), {'email': 'cooldown@example.com'})
        mail.outbox.clear()
        self.client.post(reverse('resend_confirmation'), {'email': 'cooldown@example.com'})
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_exhausting_daily_limit_stops_sending_but_never_errors(self):
        """Story 3.2, 3o AC: esgotado o limite de 5 reenvios por dia, a conta continua existindo
        e a tela nao trava -- so para de mandar e-mail novo. Usa o contador proprio (cache key
        dedicada, ver ResendConfirmationEmailView._daily_limit_cache_key) -- mudar
        RESEND_DAILY_LIMIT pra outro valor faz este teste reagir de verdade, ao contrario da
        primeira versao (achada quebrada na revisao) que compartilhava estado com o cooldown."""
        from apps.accounts.views import RESEND_DAILY_LIMIT_SECONDS, ResendConfirmationEmailView
        from django.core.cache import cache

        self.client.post(reverse('account_signup'), {'email': 'limitediario@example.com'})
        mail.outbox.clear()

        view = ResendConfirmationEmailView()
        cache_key = view._daily_limit_cache_key('limitediario@example.com')
        cache.set(cache_key, 5, RESEND_DAILY_LIMIT_SECONDS)

        response = self.client.post(
            reverse('resend_confirmation'), {'email': 'limitediario@example.com'}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertTrue(User.objects.filter(email='limitediario@example.com').exists())

    def test_resend_daily_limit_reacts_to_a_lower_configured_limit(self):
        """Prova que o teste acima realmente exercita RESEND_DAILY_LIMIT (nao um numero
        hard-coded coincidente): com o limite reduzido pra 1, um UNICO reenvio ja esgota a cota."""
        from unittest.mock import patch

        self.client.post(reverse('account_signup'), {'email': 'limitebaixo@example.com'})
        mail.outbox.clear()
        self._clear_rate_limit('limitebaixo@example.com')

        with patch('apps.accounts.views.RESEND_DAILY_LIMIT', 1):
            self.client.post(reverse('resend_confirmation'), {'email': 'limitebaixo@example.com'})
            self.assertEqual(len(mail.outbox), 1)

            self._clear_rate_limit('limitebaixo@example.com')
            self.client.post(reverse('resend_confirmation'), {'email': 'limitebaixo@example.com'})
            self.assertEqual(len(mail.outbox), 1)

    def test_resend_for_unknown_email_does_not_error_and_shows_generic_message(self):
        response = self.client.post(
            reverse('resend_confirmation'), {'email': 'naoexiste@example.com'}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_uses_session_email_when_form_field_absent(self):
        self.client.post(reverse('account_signup'), {'email': 'sessao@example.com'})
        mail.outbox.clear()
        self._clear_rate_limit('sessao@example.com')
        self.client.post(reverse('resend_confirmation'), {})
        self.assertEqual(len(mail.outbox), 1)


class ExpiredConfirmationLinkTests(TestCase):
    """Story 3.4: vinculo expirado/invalido -- ACCOUNT_CONFIRM_EMAIL_ON_GET=True ja confirma e
    redireciona no GET quando a chave e valida, entao esta tela so aparece com chave invalida."""

    def test_invalid_key_shows_expired_message_with_resend_form(self):
        response = self.client.get(reverse('account_confirm_email', kwargs={'key': 'chave-invalida-123'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vinculo expirado ou invalido')
        self.assertContains(response, 'name="email"')

    def test_invalid_key_never_authenticates(self):
        response = self.client.get(reverse('account_confirm_email', kwargs={'key': 'chave-invalida-456'}))
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class RequireCompleteAccountMiddlewareTests(TestCase):
    """Story 3.5: nome/sobrenome obrigatorios no primeiro login."""

    def test_incomplete_profile_redirects_to_complete_profile(self):
        user = User.objects.create_user(
            email='incompleto@example.com', password='SenhaForte123', profile_completed=False,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertRedirects(response, f"{reverse('complete_profile')}?next={reverse('home')}")

    def test_toggle_theme_is_exempt_from_the_gate(self):
        """Regressao encontrada na revisao: toggle_theme e renderizado em toda pagina (cabecalho),
        inclusive a propria tela de completar perfil -- sem a excecao, o clique so redirecionava
        de volta pra complete_profile, sem alternar o tema e sem sinal de erro."""
        user = User.objects.create_user(
            email='temaincompleto@example.com', password='SenhaForte123', profile_completed=False,
        )
        self.client.force_login(user)
        response = self.client.post(reverse('toggle_theme'), HTTP_REFERER='/')
        self.assertNotEqual(response.url, f"{reverse('complete_profile')}?next=%2F")
        user.refresh_from_db()
        self.assertEqual(user.preferred_theme, 'dark')

    def test_completing_profile_clears_the_gate(self):
        user = User.objects.create_user(
            email='completando@example.com', password='SenhaForte123', profile_completed=False,
        )
        self.client.force_login(user)
        self.client.post(reverse('complete_profile'), {'first_name': 'Fulano', 'last_name': 'Silva'})
        user.refresh_from_db()
        self.assertTrue(user.profile_completed)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_completing_profile_redirects_to_the_original_destination(self):
        """O middleware embute ?next=<caminho original> ao redirecionar -- completar o perfil
        tem que voltar pra la, nao sempre pra home (senao um POST interrompido em outra tela
        nunca teria como retomar de onde parou)."""
        user = User.objects.create_user(
            email='voltandopraestatisticas@example.com', password='SenhaForte123', profile_completed=False,
        )
        self.client.force_login(user)
        response = self.client.post(
            f"{reverse('complete_profile')}?next={reverse('statistics')}",
            {'first_name': 'Fulano', 'last_name': 'Silva'},
        )
        self.assertRedirects(response, reverse('statistics'))

    def test_completing_profile_rejects_unsafe_next_and_falls_back_to_home(self):
        """Regressao encontrada na revisao: 'next' era usado sem nenhuma validacao de host/esquema
        -- um link tipo ?next=https://phishing.example seria seguido as cegas logo apos o usuario
        confirmar a propria senha, um vetor de phishing crivel (o clique inicial e em dominio
        real)."""
        user = User.objects.create_user(
            email='naoredireciona@example.com', password='SenhaForte123', profile_completed=False,
        )
        self.client.force_login(user)
        response = self.client.post(
            f"{reverse('complete_profile')}?next=https://phishing.example/",
            {'first_name': 'Fulano', 'last_name': 'Silva'},
        )
        self.assertRedirects(response, reverse('home'))

    def test_staff_user_is_never_gated(self):
        staff = User.objects.create_user(
            email='staff@example.com', password='SenhaForte123', is_staff=True, profile_completed=False,
        )
        self.client.force_login(staff)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_admin_path_is_never_gated(self):
        """Regressao encontrada na revisao: com um SUPERUSER, a excecao de path nunca chega a
        ser exercitada (a excecao de papel -- is_staff/is_superuser -- ja intercepta antes).
        Usa um usuario comum (nao-staff) especificamente pra provar que EXEMPT_PATH_PREFIXES
        em si funciona -- o Django admin vai redirecionar pro proprio login dele, mas o destino
        nunca pode ser complete_profile."""
        user = User.objects.create_user(
            email='naoadmin@example.com', password='SenhaForte123', profile_completed=False,
        )
        self.client.force_login(user)
        response = self.client.get('/admin/alguma-coisa/')
        if response.status_code == 302:
            self.assertNotIn('complete-profile', response.url)

    def test_admin_path_prefix_exemption_directly(self):
        """Exercita EXEMPT_PATH_PREFIXES isoladamente, sem depender do proprio Django admin
        (que tem seu proprio gate de is_staff, o que mascara o comportamento do middleware)."""
        from apps.accounts.middleware import RequireCompleteAccountMiddleware
        from django.test import RequestFactory

        user = User.objects.create_user(
            email='pathexempt@example.com', password='SenhaForte123', profile_completed=False,
        )
        request = RequestFactory().get('/admin/qualquer-coisa/')
        request.user = user
        called = []
        middleware = RequireCompleteAccountMiddleware(lambda req: called.append(req) or 'ok')
        result = middleware(request)
        self.assertEqual(result, 'ok')
        self.assertEqual(len(called), 1)

    def test_complete_profile_does_not_reappear_on_subsequent_logins(self):
        user = User.objects.create_user(
            email='naoreaparece@example.com', password='SenhaForte123', profile_completed=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)


class ProfileCompletedDataMigrationTests(TestCase):
    """Story 3.5, grandfather clause: contas ja existentes no momento do deploy nunca sao pegas
    pelo gate. Exercita a funcao de dados da migration diretamente contra o app registry real
    (nome do modulo comeca com digito, entao precisa de importlib em vez de 'import' direto)."""

    def test_migration_marks_existing_users_as_profile_completed(self):
        import importlib
        from django.apps import apps as real_apps

        migration_module = importlib.import_module('apps.accounts.migrations.0002_user_profile_completed')

        old_user = User.objects.create_user(
            email='antigo@example.com', password='SenhaForte123', profile_completed=False,
        )
        new_user = User.objects.create_user(
            email='outro-antigo@example.com', password='SenhaForte123', profile_completed=False,
        )

        migration_module.mark_existing_users_as_profile_completed(real_apps, None)

        old_user.refresh_from_db()
        new_user.refresh_from_db()
        self.assertTrue(old_user.profile_completed)
        self.assertTrue(new_user.profile_completed)


class FullSignupJourneyTests(TestCase):
    """Smoke test de fechamento do Epic 2 (Story 3.5, AC final): a UJ-2 inteira numa passada so
    -- cadastro so com e-mail -> confirmacao -> criacao de senha -> login -> nome/sobrenome ->
    home -- sem travar em nenhum ponto. Extrai a URL de confirmacao REAL do corpo do e-mail
    enviado (nao reconstroi a chave manualmente), pra provar que o encadeamento ponta-a-ponta
    de verdade funciona, nao so cada pedaco isolado."""

    def test_full_journey_from_signup_to_home(self):
        email = 'jornadacompleta@example.com'

        signup_response = self.client.post(reverse('account_signup'), {'email': email}, follow=True)
        self.assertRedirects(signup_response, reverse('account_email_verification_sent'))
        self.assertContains(signup_response, email)
        self.assertEqual(len(mail.outbox), 1)

        confirmation_url_match = re.search(r'https?://[^\s]+/accounts/confirm-email/[^\s]+/', mail.outbox[0].body)
        self.assertIsNotNone(confirmation_url_match, 'e-mail de confirmacao sem link reconhecivel')
        confirmation_path = confirmation_url_match.group(0).split('testserver', 1)[-1]
        confirmation_path = re.sub(r'^https?://[^/]+', '', confirmation_path)

        confirm_response = self.client.get(confirmation_path, follow=True)
        self.assertEqual(confirm_response.status_code, 200)
        password_form_url = confirm_response.redirect_chain[-1][0]
        self.assertIn('/accounts/password/reset/key/', password_form_url)

        password_response = self.client.post(password_form_url, {
            'password1': 'SenhaForte123!', 'password2': 'SenhaForte123!', 'terms_accepted': 'on',
        }, follow=True)
        self.assertTrue(password_response.context['user'].is_authenticated)

        user = User.objects.get(email=email)
        self.assertTrue(user.has_usable_password())
        self.assertFalse(user.profile_completed)
        complete_profile_url = password_response.redirect_chain[-1][0]
        self.assertIn('complete-profile', complete_profile_url)

        final_response = self.client.post(
            complete_profile_url, {'first_name': 'Jornada', 'last_name': 'Completa'}, follow=True
        )
        self.assertEqual(final_response.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.profile_completed)

        home_response = self.client.get(reverse('home'))
        self.assertEqual(home_response.status_code, 200)
