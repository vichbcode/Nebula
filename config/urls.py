"""
URL configuration for config project.
"""
import os

from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

# URL d'administration non devinable (surchargée par DJANGO_ADMIN_URL dans .env).
_ADMIN_PATH = os.environ.get('DJANGO_ADMIN_URL', 'nebula-7f3k-admin/') or 'nebula-7f3k-admin/'

urlpatterns = [
    path(_ADMIN_PATH, admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('mentions-legales/', TemplateView.as_view(template_name='legal/mentions_legales.html'), name='mentions_legales'),
    path('politique-de-confidentialite/', TemplateView.as_view(template_name='legal/politique_confidentialite.html'), name='politique_confidentialite'),
    path('', include('communities.urls')),
]