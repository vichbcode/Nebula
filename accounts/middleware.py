"""Middleware : suivi de l’activité et bannissement immédiat."""

from datetime import timedelta

from django.utils import timezone

ONLINE_WINDOW = timedelta(minutes=10)


class OnlineMiddleware:
    """Met à jour last_seen de l’utilisateur connecté (throttlé à ~1 min)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            now = timezone.now()
            stale = user.last_seen is None or (now - user.last_seen) > timedelta(minutes=1)
            if stale:
                User = user.__class__
                User.objects.filter(pk=user.pk).update(last_seen=now)
                user.last_seen = now
        return self.get_response(request)


class BanMiddleware:
    """Déconnecte immédiatement les utilisateurs bannis."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and user.is_banned:
            from django.contrib.auth import logout
            userId = user.pk
            was_guest = user.is_guest
            logout(request)
            if was_guest:
                from .models import User
                User.objects.filter(pk=userId).delete()
            from django.shortcuts import redirect
            return redirect('communities:index')
        return self.get_response(request)