"""
Django settings for config project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env_bool(name, default='0'):
    """Lit une variable d'environnement comme booléen ('1'/'0')."""
    return os.environ.get(name, default).strip().lower() in {'1', 'true', 'yes', 'on'}


SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

DEBUG = env_bool('DJANGO_DEBUG', '0')

_allowed = os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')
if os.environ.get('VERCEL'):
    _allowed += ',.vercel.app'
ALLOWED_HOSTS = [
    h.strip()
    for h in _allowed.split(',')
    if h.strip()
]


# Application definition

INSTALLED_APPS = [
    'config.apps.NebulaAdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'communities',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'config.security.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.OnlineMiddleware',
    'accounts.middleware.BanMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.template.context_processors.csrf',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.site_info',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


def _database_opts():
    """Options de connexion (ex. sslmode pour Neon)."""
    from urllib.parse import parse_qs, urlparse

    opts = {}
    url = os.environ.get('DATABASE_URL', '')
    if url:
        qs = parse_qs(urlparse(url).query)
        if qs.get('sslmode'):
            opts['sslmode'] = qs['sslmode'][0]
    sslmode = (os.environ.get('DB_SSLMODE', '') or '').strip()
    if sslmode:
        opts['sslmode'] = sslmode
    return opts or None


def _db_from_url(url):
    from urllib.parse import urlparse

    parsed = urlparse(url)
    conf = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': parsed.path.lstrip('/'),
        'USER': parsed.username,
        'PASSWORD': parsed.password,
        'HOST': parsed.hostname,
        'PORT': parsed.port,
        'CONN_MAX_AGE': 60,
    }
    opts = _database_opts()
    if opts:
        conf['OPTIONS'] = opts
    return conf


def _db_from_env():
    conf = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'nebula'),
        'USER': os.environ.get('DB_USER', 'nebula_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 60,
    }
    opts = _database_opts()
    if opts:
        conf['OPTIONS'] = opts
    return conf


DATABASES = {
    'default': (
        _db_from_url(os.environ['DATABASE_URL'])
        if os.environ.get('DATABASE_URL') else _db_from_env()
    )
}


AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'fr-fr'

TIME_ZONE = 'Europe/Paris'

USE_I18N = True

USE_TZ = True


STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'accounts:login'

# Seuils de présence en ligne (minutes)
GUEST_ONLINE_MINUTES = 10


# ---- Sécurité des sessions, cookies et transports ----
_HTTPS = env_bool('DJANGO_HTTPS', '0')  # '1' une fois déployé derrière HTTPS

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = _HTTPS
# Durée de vie des sessions (s) : 14 jours par défaut.
SESSION_COOKIE_AGE = int(os.environ.get('SESSION_COOKIE_AGE', '1209600'))
# Session éphémère (fermeture du navigateur) si activé via l'environnement.
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool('SESSION_EXPIRE_AT_BROWSER_CLOSE', '0')
# Note : la rotation de clé de session à la connexion est déjà assurée par
# django.contrib.auth.login() (request.session.cycle_key()).

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = _HTTPS

CSRF_TRUSTED_ORIGINS = [
    f'https://{host}'
    for host in ALLOWED_HOSTS
    if host not in {'localhost', '127.0.0.1'}
]

if _HTTPS:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# ---- Content-Security-Policy ----
# Le code utilise beaucoup de scripts/styles inline (détails d'appel…) :
# 'unsafe-inline' est donc conservé, mais les origines externes sont verrouillées
# (CDN LiveKit uniquement, domaine calculé depuis LIVEKIT_URL). En production,
# préférez déplacer l'inline vers des fichiers pour resserrer la politique.
def _csp_connect_extra():
    from urllib.parse import urlparse

    livekit = (os.environ.get('LIVEKIT_URL', '') or '').strip()
    if not livekit:
        return ''
    host = urlparse(livekit).hostname
    if not host:
        return ''
    return f'https://{host} wss://{host}'


__CSP_CONNECT = ' '.join(x for x in ["'self'", _csp_connect_extra()] if x)
CSP_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none'; "
    "frame-src 'none'; "
    "form-action 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "media-src 'self' blob: data:; "
    f"connect-src {__CSP_CONNECT}; "
)
CSP_ENABLED = env_bool('CSP_ENABLED', '1')
# Passez à 1 pour tester la CSP sans rien bloquer (rapport console du navigateur).
CSP_REPORT_ONLY = env_bool('CSP_REPORT_ONLY', '0')


# ---- Relais TURN pour les appels vidéo ----
# Si vide, les appels restent en pair-à-pair simple (STUN) : marche sur le même
# réseau, ne masque pas l'IP. Configurez un serveur coturn puis remplissez ces
# valeurs pour activer le relais (connexion multi-réseaux + IP masquée).
TURN_URLS = os.environ.get('TURN_URLS', '').strip()  # ex: 'turn:turn.example.com:3478?transport=udp'
TURN_SECRET = os.environ.get('TURN_SECRET', '').strip()  # clé partagée (Coturn use-auth-secret)
TURN_USERNAME = os.environ.get('TURN_USERNAME', '').strip()  # login (si pas de TURN REST)
TURN_PASSWORD = os.environ.get('TURN_PASSWORD', '').strip()  # mot de passe (si pas de TURN REST)
TURN_TTL = int(os.environ.get('TURN_TTL', '3600'))  # durée de vie des identifiants (s)

# ---- LiveKit Cloud (appels vidéo) ----
# Infrastructure d'appel gratuite (5 000 min de participants/mois). Avant la
# configuration, les appels restent en pai-à-pair maison (WebRTC).
LIVEKIT_URL = os.environ.get('LIVEKIT_URL', '').strip()  # ex: 'wss://monprojet.livekit.cloud'
LIVEKIT_API_KEY = os.environ.get('LIVEKIT_API_KEY', '').strip()
LIVEKIT_API_SECRET = os.environ.get('LIVEKIT_API_SECRET', '').strip()