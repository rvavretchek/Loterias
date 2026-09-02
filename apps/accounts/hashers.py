import os

from django.conf import settings
from django.contrib.auth.hashers import Argon2PasswordHasher
from django.core.exceptions import ImproperlyConfigured


class PepperedArgon2PasswordHasher(Argon2PasswordHasher):
    """Hasher Argon2id do Django com pepper externo ao banco."""
    algorithm = 'argon2id_peppered'

    def _with_pepper(self, password):
        pepper = os.getenv('PASSWORD_PEPPER', getattr(settings, 'PASSWORD_PEPPER', '')).strip()
        if not pepper:
            raise ImproperlyConfigured('PASSWORD_PEPPER must be configured.')
        return f'{password}{pepper}'

    def encode(self, password, salt, **kwargs):
        return super().encode(self._with_pepper(password), salt, **kwargs)

    def verify(self, password, encoded, **kwargs):
        return super().verify(self._with_pepper(password), encoded, **kwargs)
