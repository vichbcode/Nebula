"""Site d'administration Django restreint.

L'accès à l'admin est réservé aux utilisateurs actifs ayant is_staff ET
(is_site_admin — l'admin « métier » du site — ou is_superuser). L'URL reste
configurable via DJANGO_ADMIN_URL pour ne pas exposer une route connue.
"""

from django.contrib.admin import AdminSite


class NebulaAdminSite(AdminSite):
    def __init__(self, name='nebula_admin'):
        super().__init__(name)
        self.site_header = 'Administration Nébula'
        self.site_title = 'Nébula Admin'
        self.index_title = 'Gestion du site'

    def has_permission(self, request):
        user = request.user
        return bool(
            user.is_active
            and user.is_staff
            and (user.is_site_admin or user.is_superuser)
        )


site = NebulaAdminSite()