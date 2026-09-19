"""Aide à l’intégration LiveKit Cloud (jetons JWT + fermeture de salon)."""

from datetime import timedelta

from django.conf import settings

try:
    from livekit import api
except ImportError:  # paquet optionnel s'il n'est pas installé
    api = None


def is_enabled():
    """Le service LiveKit est-il configuré ?"""
    return all([api, settings.LIVEKIT_URL,
                settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET])


def room_name_for(call):
    """Nom stable du salon LiveKit rattaché à un appel."""
    return f'{call.community.slug}-{call.pk}'


def access_token(call, user, identity):
    """Jeton JWT pour rejoindre le salon d'un appel.

    Le jeton est très court (60 s) ; le client l'échange aussitôt contre une
    connexion au salon.
    """
    token = api.AccessToken(
        settings.LIVEKIT_API_KEY,
        settings.LIVEKIT_API_SECRET,
    )
    grant = api.VideoGrants(room_join=True, room=room_name_for(call))
    name = getattr(user, 'username', None) or identity
    return (token.with_identity(identity).with_name(name)
            .with_ttl(timedelta(seconds=60)).with_grants(grant).to_jwt())


def close_room(call):
    """Ferme le salon LiveKit d'un appel : déconnecte tous ses participants."""
    if not is_enabled():
        return
    import asyncio

    async def _run():
        client = api.LiveKitAPI(
            settings.LIVEKIT_URL,
            settings.LIVEKIT_API_KEY,
            settings.LIVEKIT_API_SECRET,
        )
        try:
            await client.room.delete_room(
                api.DeleteRoomRequest(room=room_name_for(call))
            )
        finally:
            await client.aclose()

    try:
        asyncio.run(_run())
    except Exception:
        pass  # le salon n'existe pas forcément : ce n'est pas bloquant