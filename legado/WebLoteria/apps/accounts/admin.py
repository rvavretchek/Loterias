from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Tenant, Domain, User


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'email', 'ativo', 'criado_em')
    list_filter = ('ativo', 'criado_em')
    search_fields = ('nome', 'slug', 'email')
    prepopulated_fields = {'slug': ('nome',)}


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')
    list_filter = ('is_primary',)
    search_fields = ('domain', 'tenant__nome')


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'tenant', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'tenant', 'tema_preferido')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informacoes Pessoais', {'fields': ('first_name', 'last_name', 'telefone', 'bio', 'avatar')}),
        ('Organizacao', {'fields': ('tenant',)}),
        ('Preferencias', {'fields': ('tema_preferido',)}),
        ('Permissoes', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Datas Importantes', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'tenant'),
        }),
    )
