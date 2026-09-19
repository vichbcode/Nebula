from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'is_guest', 'is_site_admin', 'is_banned', 'last_seen')
    list_filter = ('is_guest', 'is_site_admin', 'is_banned', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Compte', {'fields': ('is_guest', 'is_site_admin', 'is_banned', 'last_seen')}),
    )