"""loterias_project URL Configuration."""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('conta/', include('accounts.urls')),
    path('', include('jogos.urls')),
]
