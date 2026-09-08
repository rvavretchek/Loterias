import os

from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings

from apps.accounts.hashers import PepperedArgon2PasswordHasher
from apps.accounts.models import User


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
