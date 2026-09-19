"""Contexte global injecté dans tous les templates."""

from communities.models import Community


def site_info(request):
    return {
        'SITE_NAME': 'Nébula',
        'total_community_count': Community.objects.count(),
    }