from django.db import models
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser


class UserManager(BaseUserManager):
    """Manager para User com e-mail como identificador (sem username)."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O e-mail e obrigatorio.')
        email = self.normalize_email(email)
        # 'Perfil pendente' (Story 3.5) e um conceito exclusivo do fluxo publico de cadastro
        # so-com-email (que constroi o User direto via o adapter do allauth, nunca por este
        # manager) -- create_user() e usado por createsuperuser/scripts/testes, que sempre
        # esperam uma conta pronta pra uso, a nao ser que o chamador diga o contrario.
        extra_fields.setdefault('profile_completed', True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser precisa ter is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser precisa ter is_superuser=True.')
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Usuario customizado com suporte a email."""
    username = None
    email = models.EmailField(unique=True, verbose_name='E-mail')
    preferred_theme = models.CharField(
        max_length=10,
        choices=[('light', 'Claro'), ('dark', 'Escuro')],
        default='light',
        verbose_name='Tema Preferido'
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        verbose_name='Avatar'
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name='Telefone')
    bio = models.TextField(blank=True, verbose_name='Biografia')
    profile_completed = models.BooleanField(
        default=False,
        verbose_name='Perfil completo',
        help_text='Nome e sobrenome informados no primeiro login (Story 3.5).',
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_initials(self):
        names = self.get_full_name().split()
        if len(names) >= 2:
            return f"{names[0][0]}{names[-1][0]}".upper()
        return self.email[0].upper() if self.email else '?'
