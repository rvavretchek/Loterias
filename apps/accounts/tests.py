import os

from django.test import SimpleTestCase

from apps.accounts.hashers import PepperedArgon2PasswordHasher


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
