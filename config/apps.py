"""Config d'app de config : échange l'AdminSite Django par défaut."""

from django.contrib.admin.apps import AdminConfig


class NebulaAdminConfig(AdminConfig):
    default_site = 'config.admin.NebulaAdminSite'