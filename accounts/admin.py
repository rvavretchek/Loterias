from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'first_name', 'email_confirmed', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff', 'email_confirmed')
    search_fields = ('email', 'first_name')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informações Pessoais', {'fields': ('first_name',)}),
        ('Preferências', {'fields': ('tema_preferido',)}),
        ('Permissões', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                    'email_confirmed', 'groups', 'user_permissions')}),
        ('Datas', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'password1', 'password2'),
        }),
    )
