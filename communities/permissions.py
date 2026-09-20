"""Helper de permissions partagé par les vues et templates."""

from django.conf import settings

from .models import Membership


def perms_for(user, community):
    """Retourne un dictionnaire de permissions pour (user, community)."""
    empty = {
        'is_site_admin': False,
        'is_sub_admin': False,
        'is_member': False,
        'manage_members': False,
        'moderate': False,
        'edit_community': False,
        'ban_users': False,
        'launch_calls': False,
        'toggle_guests': False,
        'manage_subadmins': False,
    }
    if not user.is_authenticated:
        return empty

    site_admin = user.is_site_admin
    membership = community.user_membership(user)
    is_sub = membership is not None and membership.role == Membership.ROLE_SUB_ADMIN

    return {
        'is_site_admin': site_admin,
        'is_sub_admin': is_sub,
        'is_member': site_admin or membership is not None,
        'manage_members': site_admin or (membership and membership.can_manage_members),
        'moderate': site_admin or (membership and membership.can_moderate),
        'edit_community': site_admin or (membership and membership.can_edit_community),
        'ban_users': site_admin or (membership and membership.can_ban_users),
        'launch_calls': site_admin or (membership and membership.can_launch_calls),
        'toggle_guests': site_admin,
        'manage_subadmins': site_admin or (membership and membership.can_manage_subadmins),
    }


def can_access(user, community):
    """Décide si un utilisateur peut entrer (voir) dans une communauté."""
    if not user.is_authenticated:
        return False
    if user.is_banned:
        return False
    if user.is_site_admin:
        return True
    if community.admins_only:
        return False
    if user.is_guest:
        return community.guests_allowed
    return True


def can_post(user, community):
    if not user.is_authenticated or user.is_banned:
        return False
    if user.is_site_admin:
        return True
    return community.user_membership(user) is not None