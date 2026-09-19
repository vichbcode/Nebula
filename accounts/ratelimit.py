"""Rate-limiting sans dépendance externe, basé sur le cache Django.

Anti brute-force / spam de comptes invités. En production, mettez en place
un cache partagé (Redis, Memcached…) : le cache local (LocMemCache) est
volatile et par processus, mais suffisant ici.
"""

from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse

_LIMIT_MESSAGE = 'Trop de tentatives. Réessaie dans quelques minutes.'


def client_ip(request):
    """Adresse IP du client (gère un reverse-proxy qui pose X-Forwarded-For)."""
    ip = request.META.get('REMOTE_ADDR', '?').strip()
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        ip = forwarded.split(',')[0].strip() or ip
    return ip[:64]


def _client_key(request):
    """Clé par client : utilisateur connecté si possible, sinon IP."""
    if request.user.is_authenticated:
        return f'u{request.user.pk}'
    return f'ip{client_ip(request)}'


def ratelimit(prefix, limit, window=900, key=None):
    """Limite à `limit` appels POST par `window` secondes par client.

    Les requêtes GET n'émettent jamais (pages de formulaire) : seul le POST
    consomme du quota.
    """
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method == 'POST':
                client = key(request) if key else _client_key(request)
                cache_key = f'rl:{prefix}:{client}'
                if not cache.add(cache_key, 1, window):
                    try:
                        count = cache.incr(cache_key)
                    except ValueError:
                        count = 1
                else:
                    count = 1
                request.rate_limit_remaining = limit - count
                if count > limit:
                    return HttpResponse(_LIMIT_MESSAGE, status=429)
            return view(request, *args, **kwargs)
        return wrapper
    return decorator