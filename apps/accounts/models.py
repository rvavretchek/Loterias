from django.db import models
from django.contrib.auth.models import AbstractUser
from django_sqlite_tenants.models import TenantMixin, DomainMixin


class Tenant(TenantMixin):
    """Modelo de tenant para multitenancy com SQLite."""
    nome = models.CharField(max_length=100, verbose_name='Nome da Organizacao')
    slug = models.SlugField(unique=True, verbose_name='Identificador')
    email = models.EmailField(verbose_name='E-mail')
    ativo = models.BooleanField(default=True, verbose_name='Ativo')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')

    class Meta:
        verbose_name = 'Organizacao'
        verbose_name_plural = 'Organizacoes'

    def __str__(self):
        return self.nome


class Domain(DomainMixin):
    """Dominios associados aos tenants."""
    class Meta:
        verbose_name = 'Dominio'
        verbose_name_plural = 'Dominios'

    def __str__(self):
        return self.domain


class User(AbstractUser):
    """Usuario customizado com suporte a email."""
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    email = models.EmailField(unique=True, verbose_name='E-mail')
    tenant = models.ForeignKey(
        Tenant, 
        on_delete=models.CASCADE, 
        related_name='usuarios',
        null=True,
        blank=True,
        verbose_name='Organizacao'
    )
    tema_preferido = models.CharField(
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
    telefone = models.CharField(max_length=20, blank=True, verbose_name='Telefone')
    bio = models.TextField(blank=True, verbose_name='Biografia')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

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
