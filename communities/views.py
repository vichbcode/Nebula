"""Vues des communautés et de l’espace d’administration du site."""

import base64
import hashlib
import hmac
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Q
from django.db.transaction import atomic
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .forms import (CommunityEditForm, CommunityForm, MessageForm, SubAdminRightsForm,
                    SupportReplyForm, SupportStartForm)
from .livekit import access_token, close_room, is_enabled
from .models import (CallSignal, Community, CommunityCall, Membership, Message,
                     SupportMessage, SupportThread)
from .permissions import can_access, can_post, perms_for

User = get_user_model()


def index(request):
    if request.user.is_authenticated:
        return redirect('communities:home')
    return redirect('accounts:welcome')


@login_required
@never_cache
def home(request):
    user = request.user
    if user.is_guest:
        communities = Community.objects.filter(guests_allowed=True)
    elif user.is_site_admin:
        communities = Community.objects.all()
    else:
        communities = Community.objects.all()

    cards = []
    for c in communities:
        perms = perms_for(user, c)
        membership = c.user_membership(user)
        cards.append({
            'community': c,
            'perms': perms,
            'membership': membership,
            'role': c.user_role(user),
            'member_count': c.member_count(),
        })
    support = Community.objects.filter(is_support=True).first()
    return render(request, 'communities/home.html', {
        'cards': cards,
        'admins': User.objects.filter(is_site_admin=True, is_banned=False).order_by('username'),
        'support': support,
    })


@never_cache
def community_detail(request, slug):
    community = get_object_or_404(Community, slug=slug)
    user = request.user
    has_access = user.is_authenticated and can_access(user, community)

    if not has_access:
        if not user.is_authenticated:
            return redirect('accounts:welcome')
        return render(request, 'communities/no_access.html', {'community': community})

    perms = perms_for(user, community)
    membership = community.user_membership(user)
    messages_qs = community.messages.select_related('author')[:200]
    members = community.memberships.select_related('user').filter(
        user__is_banned=False
    ).order_by('-role', 'joined_at')

    active_call = community.calls.first()
    is_registered = user.is_authenticated and not user.is_guest
    if active_call:
        mode = 'livekit' if is_enabled() else 'p2p'
        print(f'[CALL] PAGE user={getattr(user, "username", "anonyme")} call={active_call.pk} starter={active_call.started_by_id} mode={mode}', flush=True)
    context = {
        'community': community,
        'perms': perms,
        'membership': membership,
        'role': community.user_role(user),
        'chat_messages': messages_qs,
        'last_chat_pk': max((m.pk for m in messages_qs), default=0),
        'members': members,
        'message_form': MessageForm() if perms['is_member'] else None,
        'active_call': active_call,
        'call_can_start': (user.is_site_admin or perms['launch_calls']) and not active_call,
        'call_can_join': is_registered and active_call is not None,
        'call_is_starter': bool(
            active_call and user.is_authenticated
            and active_call.started_by_id == user.pk
        ),
        # LiveKit (SFU) disponible si configuré ; sinon repli pair-à-pair maison.
        'livekit_service': is_enabled(),
        # identity LiveKit -> pseudo, pour afficher le vrai nom dans les appels.
        'call_name_map': {
            f'{community.slug}-{m.user.pk}': m.user.username
            for m in members
            if m.user and not m.user.is_guest
        },
    }

    if community.is_support and user.is_authenticated:
        if user.is_site_admin:
            context['support_requests'] = (
                SupportThread.objects
                .filter(community=community, deleted=False)
                .annotate(unread=Count(
                    'messages',
                    filter=Q(messages__author=F('user'), messages__is_read=False),
                ))
                .select_related('user', 'admin')
                .order_by('-updated_at')
            )
        else:
            context['support_form'] = SupportStartForm(user=user)
            context['support_threads'] = (
                user.support_threads
                .filter(community=community, deleted=False)
                .annotate(unread=Count(
                    'messages',
                    filter=Q(messages__author=F('admin'), messages__is_read=False),
                ))
                .select_related('admin')
                .order_by('-updated_at')
            )

    return render(request, 'communities/detail.html', context)


# ---------------------------------------------------------------------------
# Assistance : discussion 1-à-1 dans la communauté support (invités + inscrits)
# ---------------------------------------------------------------------------

def _support_access(user, thread):
    """Un demandeur, l’admin désigné, ou n’importe quel admin du site."""
    if not user.is_authenticated or user.is_banned:
        return False
    if user.is_site_admin:
        return True
    return thread.user_id == user.pk


@login_required
def support_start(request, slug):
    community = get_object_or_404(Community, slug=slug)
    user = request.user
    if request.method == 'POST' and community.is_support and can_access(user, community):
        form = SupportStartForm(request.POST, user=user)
        if form.is_valid():
            admin = form.cleaned_data['admin']
            if admin == user:
                messages.error(request, 'Tu ne peux pas te contacter toi-même.')
                return redirect('communities:detail', slug=community.slug)
            thread = (
                SupportThread.objects
                .filter(community=community, user=user)
                .filter(admin=admin)
                .first()
            )
            if thread is None:
                thread = SupportThread.objects.create(
                    community=community, user=user, admin=admin
                )
            elif thread.deleted:
                thread.deleted = False
                thread.deleted_by = None
                thread.deleted_at = None
                thread.save(update_fields=['deleted', 'deleted_by', 'deleted_at', 'updated_at'])
            if thread.status != SupportThread.STATUS_OPEN:
                thread.status = SupportThread.STATUS_OPEN
                thread.save(update_fields=['status', 'updated_at'])
            SupportMessage.objects.create(
                thread=thread, author=user, text=form.cleaned_data['text']
            )
            messages.success(request, f'Discussion ouverte avec {admin.username}.')
            return redirect('communities:support_thread', slug=community.slug, thread_pk=thread.pk)
        messages.error(request, 'Choisis un administrateur et écris un message.')
    return redirect('communities:detail', slug=community.slug)


@login_required
def support_thread(request, slug, thread_pk):
    community = get_object_or_404(Community, slug=slug)
    thread = get_object_or_404(
        SupportThread, pk=thread_pk, community=community
    )
    if not _support_access(request.user, thread):
        messages.error(request, 'Tu n\'as pas accès à cette discussion.')
        return redirect('communities:detail', slug=community.slug)

    user = request.user
    if user.is_site_admin:
        thread.messages.filter(author=thread.user, is_read=False).update(is_read=True)
    elif thread.admin_id:
        thread.messages.filter(author=thread.admin, is_read=False).update(is_read=True)

    return render(request, 'communities/support_thread.html', {
        'community': community,
        'thread': thread,
        'deleted_notice': True if thread.deleted else False,
        'smsgs': thread.messages.select_related('author'),
        'reply_form': SupportReplyForm(),
    })


@login_required
def support_reply(request, slug, thread_pk):
    community = get_object_or_404(Community, slug=slug)
    thread = get_object_or_404(SupportThread, pk=thread_pk, community=community)
    if request.method != 'POST' or not _support_access(request.user, thread):
        messages.error(request, 'Tu n\'as pas accès à cette discussion.')
        return redirect('communities:detail', slug=community.slug)
    if thread.deleted:
        messages.error(request, 'Cette conversation a été supprimée par l’admin.')
        return redirect('communities:support_thread', slug=community.slug, thread_pk=thread.pk)

    form = SupportReplyForm(request.POST)
    if form.is_valid():
        SupportMessage.objects.create(
            thread=thread,
            author=request.user,
            text=form.cleaned_data['text'],
        )
        if request.user.is_site_admin:
            thread.messages.filter(author=thread.user, is_read=False).update(is_read=True)
        elif thread.admin_id:
            thread.messages.filter(author=thread.admin, is_read=False).update(is_read=True)
    return redirect('communities:support_thread', slug=community.slug, thread_pk=thread.pk)


@login_required
def support_close(request, slug, thread_pk):
    community = get_object_or_404(Community, slug=slug)
    thread = get_object_or_404(SupportThread, pk=thread_pk, community=community)
    if request.method == 'POST' and _support_access(request.user, thread):
        thread.status = SupportThread.STATUS_CLOSED
        thread.save(update_fields=['status', 'updated_at'])
        messages.info(request, 'Discussion fermée.')
    return redirect('communities:support_thread', slug=community.slug, thread_pk=thread.pk)


@login_required
def support_delete(request, slug, thread_pk):
    """Un admin du site supprime définitivement la discussion (soft-delete)."""
    community = get_object_or_404(Community, slug=slug)
    thread = get_object_or_404(SupportThread, pk=thread_pk, community=community)
    if request.method == 'POST' and request.user.is_site_admin:
        thread.deleted = True
        thread.deleted_by = request.user
        thread.deleted_at = timezone.now()
        thread.save(update_fields=['deleted', 'deleted_by', 'deleted_at', 'updated_at'])
        messages.info(request, 'Conversation supprimée. L’autre partie en est informée.')
    return redirect('communities:detail', slug=community.slug)


@login_required
def join_community(request, slug):
    if request.method == 'POST':
        community = get_object_or_404(Community, slug=slug)
        user = request.user
        exists = Membership.objects.filter(user=user, community=community).exists()
        if user.is_guest and not community.guests_allowed:
            messages.error(request, 'Les invités ne peuvent pas rejoindre cette communauté.')
        elif exists:
            messages.info(request, 'Tu es déjà membre de cette communauté.')
        else:
            Membership.objects.create(user=user, community=community, role='member')
            messages.success(request, f'Bienvenue dans {community.name} !')
        return redirect('communities:detail', slug=community.slug)
    return redirect('communities:home')


@login_required
def leave_community(request, slug):
    if request.method == 'POST':
        community = get_object_or_404(Community, slug=slug)
        Membership.objects.filter(user=request.user, community=community).delete()
        messages.info(request, f'Tu as quitté {community.name}.')
        return redirect('communities:home')
    return redirect('communities:home')


@login_required
def post_message(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if request.method == 'POST' and can_post(request.user, community):
        form = MessageForm(request.POST)
        if form.is_valid():
            form.instance.community = community
            form.instance.author = request.user
            form.save()
        return redirect('communities:detail', slug=community.slug)
    return redirect('communities:detail', slug=community.slug)


@never_cache
@require_GET
def chat_poll(request, slug):
    """Point d'accès JSON du chat temps réel : nouveaux messages + présences.

    Le client interroge ce point toutes les quelques secondes avec ?after=<pk>.
    """
    community = get_object_or_404(Community, slug=slug)
    user = request.user
    if not (user.is_authenticated and can_access(user, community)):
        return JsonResponse({'error': 'Accès refusé.'}, status=403)
    try:
        after = max(0, int(request.GET.get('after', 0)))
    except (TypeError, ValueError):
        after = 0
    new_messages = (
        community.messages
        .filter(pk__gt=after)
        .select_related('author')
        .order_by('pk')[:50]
    )
    messages = [
        {
            'pk': m.pk,
            'author': m.author.username if m.author else 'Utilisateur supprimé',
            'is_guest': bool(m.author and m.author.is_guest),
            'is_admin': bool(m.author and m.author.is_site_admin),
            'mine': bool(m.author and m.author_id == user.pk),
            'text': m.text,
            'time': timezone.localtime(m.created_at).isoformat(),
        }
        for m in new_messages
    ]
    online = [
        mb.user.username
        for mb in community.memberships
        .exclude(user__is_banned=True)
        .select_related('user')
        if mb.user.is_online
    ]
    return JsonResponse({
        'messages': messages,
        'online': online,
        'count': community.messages.count(),
    })


@login_required
def delete_message(request, slug, pk):
    message_obj = get_object_or_404(
        Message.objects.select_related('author'), pk=pk, community__slug=slug)
    perms = perms_for(request.user, message_obj.community)
    author_is_other_admin = (
        message_obj.author is not None
        and message_obj.author.is_site_admin
        and message_obj.author_id != request.user.pk
    )
    can_delete = (
        (perms['moderate'] or message_obj.author == request.user)
        and not author_is_other_admin
    )
    if request.method == 'POST' and can_delete:
        message_obj.delete()
        messages.success(request, 'Message supprimé.')
    elif request.method == 'POST':
        messages.error(request, 'Tu ne peux pas supprimer le message d’un autre administrateur.')
    return redirect('communities:detail', slug=slug)


# ---------------------------------------------------------------------------
# Gestion d’une communauté (admins du site + sous-admins selon leurs droits)
# ---------------------------------------------------------------------------

def can_manage_community(user, community):
    if not user.is_authenticated:
        return False
    if user.is_site_admin:
        return True
    m = community.user_membership(user)
    return bool(m and m.role == Membership.ROLE_SUB_ADMIN and (
        m.can_manage_members or m.can_moderate or m.can_edit_community or m.can_ban_users
    ))


@login_required
def start_call(request, slug):
    community = get_object_or_404(Community, slug=slug)
    user = request.user
    if request.method != 'POST' or user.is_guest:
        return redirect('communities:detail', slug=community.slug)
    if community.is_support:
        messages.error(request, 'Les appels ne sont pas disponibles sur cette communauté.')
        return redirect('communities:detail', slug=community.slug)
    perms = perms_for(user, community)
    if not user.is_site_admin and not perms['launch_calls']:
        messages.error(request, 'Tu n\'as pas le droit de lancer des appels.')
        return redirect('communities:detail', slug=community.slug)
    with atomic():
        # Verrouille la communauté pour empêcher deux appels simultanés
        # (course sur calls.exists() + create).
        Community.objects.select_for_update().get(pk=community.pk)
        if community.calls.exists():
            messages.error(request, 'Un appel est déjà en cours dans cette communauté.')
            return redirect('communities:detail', slug=community.slug)
        CommunityCall.objects.create(
            community=community, started_by=user, call_type=CommunityCall.CALL_VIDEO
        )
    print(f'[CALL] START by {user.username} slug={community.slug}', flush=True)
    url = reverse('communities:detail', kwargs={'slug': community.slug})
    return redirect(url + '?join=1')


@login_required
def end_call(request, slug, call_pk):
    community = get_object_or_404(Community, slug=slug)
    call = get_object_or_404(CommunityCall, pk=call_pk, community=community)
    user = request.user
    if request.method == 'POST' and (
        user.is_site_admin or call.started_by_id == user.pk
    ):
        if is_enabled():
            close_room(call)
        call.delete()
        messages.info(request, 'Appel terminé.')
        print(f'[CALL] END call={call_pk} by {user.username}', flush=True)
    return redirect('communities:detail', slug=community.slug)


@login_required
def call_signal(request, slug, call_pk):
    """Relai de signalisation WebRTC (offre, réponse, ICE) via JSON."""
    community = get_object_or_404(Community, slug=slug)
    call = get_object_or_404(CommunityCall, pk=call_pk, community=community)
    user = request.user
    if user.is_guest or user.is_banned or not can_access(user, community):
        return JsonResponse({'error': 'Accès refusé.'}, status=403)

    if request.method == 'GET':
        try:
            after = int(request.GET.get('after', 0))
        except (TypeError, ValueError):
            after = 0
        signals = list(
            CallSignal.objects.filter(call=call, pk__gt=after)
            .values('pk', 'sender', 'target', 'kind', 'data')
            .order_by('pk')
        )
        print(f'[CALL] poll user={user.username} call={call.pk} after={after} got={len(signals)}', flush=True)
        return JsonResponse({'signals': signals})

    if request.method == 'POST':
        kind = request.POST.get('kind', '')
        if kind not in {'offer', 'answer', 'ice', 'join', 'bye'}:
            return JsonResponse({'error': 'Signal invalide.'}, status=400)
        data = request.POST.get('data', '')[:20000]
        sender = request.POST.get('sender', '')[:64]
        target = request.POST.get('target', '')[:64]
        if not sender:
            return JsonResponse({'error': 'Émetteur manquant.'}, status=400)
        print(f'[CALL] post user={user.username} call={call.pk} kind={kind} sender={sender} target={target}', flush=True)
        CallSignal.objects.create(
            call=call, sender=sender, target=target, kind=kind, data=data
        )
        return JsonResponse({'ok': True})

    return JsonResponse({'error': 'Méthode non autorisée.'}, status=405)


def turn_credentials(request):
    """Identifiants TURN (time-limited) pour les appels vidéo.

    Si le relais est configuré (TURN_URLS + TURN_SECRET), génère des
    identifiants valides TURN_TTL secondes (auth REST, une par navigateur).
    Retourne un objet RTCIceServer prêt pour `iceServers`.
    """
    user = request.user
    if not user.is_authenticated or user.is_banned:
        return JsonResponse({'error': 'Accès refusé.'}, status=403)

    print(f'[CALL] turn user={user.username}', flush=True)
    urls = settings.TURN_URLS
    if not urls:
        return JsonResponse({'iceServers': []})

    turn_urls = [u.strip() for u in urls.split(',') if u.strip()]
    if settings.TURN_SECRET and settings.TURN_SECRET.strip():
        username = 'nebula'
        ttl = max(60, settings.TURN_TTL)
        expiry = int(timezone.now().timestamp()) + ttl
        full_username = f'{expiry}:{username}'
        credential = base64.b64encode(
            hmac.new(
                settings.TURN_SECRET.encode(),
                full_username.encode(),
                hashlib.sha1,
            ).digest()
        ).decode()
    else:
        full_username = settings.TURN_USERNAME
        credential = settings.TURN_PASSWORD

    return JsonResponse({
        'iceServers': [{
            'urls': turn_urls,
            'username': full_username,
            'credential': credential,
        }],
        'ttl': settings.TURN_TTL,
    })


@login_required
def livekit_token(request, slug, call_pk):
    """Jeton JWT LiveKit pour rejoindre l'appel en cours.

    Si LiveKit n'est pas configuré, répond HTTP 503 pour que le front reste
    sur la signalisation maison (WebRTC pair-à-pair).
    """
    community = get_object_or_404(Community, slug=slug)
    call = get_object_or_404(CommunityCall, pk=call_pk, community=community)
    user = request.user
    if not is_enabled():
        return JsonResponse({'error': 'LiveKit n\'est pas configuré.'}, status=503)
    if (user.is_guest or user.is_banned or not can_access(user, community)):
        return JsonResponse({'error': 'Accès refusé à l\'appel.'}, status=403)
    identity = f'{community.slug}-{user.pk}'
    room = f'{community.slug}-{call.pk}'
    print(f'[CALL] LIVEKIT token user={user.username} call={call.pk} room={room}', flush=True)
    return JsonResponse({
        'url': settings.LIVEKIT_URL,
        'token': access_token(call, user, identity),
        'identity': identity,
        'room': room,
    })


@login_required
def manage_community(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if not can_manage_community(request.user, community):
        messages.error(request, 'Tu n\'as pas l\'autorisation de gérer cette communauté.')
        return redirect('communities:detail', slug=community.slug)

    perms = perms_for(request.user, community)
    members = community.memberships.select_related('user').order_by('-role', 'joined_at')
    return render(request, 'communities/manage.html', {
        'community': community,
        'perms': perms,
        'members': members,
        'guest_form': None,
        'community_form': CommunityEditForm(instance=community)
        if perms['edit_community'] else None,
        'subadmin_form': SubAdminRightsForm() if perms['manage_subadmins'] else None,
    })


def _manage_permission(user, community, right):
    if user.is_site_admin:
        return True
    m = community.user_membership(user)
    if not m or m.role != Membership.ROLE_SUB_ADMIN:
        return False
    return getattr(m, f'can_{right}', False)


@login_required
def manage_add_member(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if request.method == 'POST' and _manage_permission(request.user, community, 'manage_members'):
        username = request.POST.get('username', '').strip().lstrip('@')
        try:
            member_user = User.objects.get(username__iexact=username, is_guest=False)
        except User.DoesNotExist:
            messages.error(request, f'Aucun utilisateur « {username} ».')
            return redirect('communities:manage', slug=community.slug)
        if membership := community.user_membership(member_user):
            messages.info(request, f'{member_user.username} est déjà membre.')
        else:
            Membership.objects.create(user=member_user, community=community, role='member')
            messages.success(request, f'{member_user.username} a été ajouté à la communauté.')
    return redirect('communities:manage', slug=community.slug)


@login_required
def manage_remove_member(request, slug, user_id):
    community = get_object_or_404(Community, slug=slug)
    if request.method == 'POST' and _manage_permission(request.user, community, 'manage_members'):
        target = get_object_or_404(User, pk=user_id)
        if target.is_site_admin:
            messages.error(request, 'Un administrateur du site ne peut pas être retiré.')
        else:
            Membership.objects.filter(community=community, user=target).delete()
            messages.success(request, 'Membre retiré de la communauté.')
    return redirect('communities:manage', slug=community.slug)


@login_required
def manage_ban_user(request, slug, user_id):
    community = get_object_or_404(Community, slug=slug)
    if request.method == 'POST' and _manage_permission(request.user, community, 'ban_users'):
        target = get_object_or_404(User, pk=user_id)
        if target.is_site_admin:
            messages.error(request, 'Un administrateur du site ne peut pas être banni.')
        elif request.user.is_site_admin:
            # Seul un admin du site bannit globalement (déconnexion + blocage partout).
            target.is_banned = True
            target.save()
            Membership.objects.filter(community=community, user=target).delete()
            messages.success(request, f'{target.username} a été banni du site et retiré de la communauté.')
        else:
            # Un sous-admin ne bannit que localement : exclusion de la communauté
            # (jamais de ban global sur tout le site).
            Membership.objects.filter(community=community, user=target).delete()
            messages.info(request, f'{target.username} a été retiré de cette communauté.')
    return redirect('communities:manage', slug=community.slug)


@login_required
def manage_unban_user(request, slug, user_id):
    community = get_object_or_404(Community, slug=slug)
    if request.method == 'POST' and request.user.is_site_admin and _manage_permission(request.user, community, 'ban_users'):
        target = get_object_or_404(User, pk=user_id)
        target.is_banned = False
        target.save()
        messages.success(request, f'{target.username} a été débloqué.')
    return redirect('communities:manage', slug=community.slug)


@login_required
def manage_toggle_guests(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if request.method == 'POST' and _manage_permission(request.user, community, 'toggle_guests'):
        community.guests_allowed = not community.guests_allowed
        community.save()
        messages.success(
            request,
            f'Accès invités : {"autorisé" if community.guests_allowed else "refusé"} pour '
            f'{community.name}.',
        )
    return redirect('communities:manage', slug=community.slug)


@login_required
def manage_edit(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if request.method == 'POST' and _manage_permission(request.user, community, 'edit_community'):
        form = CommunityEditForm(request.POST, instance=community)
        if form.is_valid():
            form.save()
            messages.success(request, 'Communauté mise à jour.')
        else:
            for field, errors in form.errors.items():
                for err in errors:
                    messages.error(request, f'{field}: {err}')
    return redirect('communities:manage', slug=community.slug)


@login_required
def manage_promote(request, slug, user_id):
    community = get_object_or_404(Community, slug=slug)
    if request.method == 'POST' and _manage_permission(request.user, community, 'manage_subadmins'):
        membership, _ = Membership.objects.get_or_create(
            user_id=user_id, community=community,
            defaults={'role': 'member'},
        )
        form = SubAdminRightsForm(request.POST, instance=membership)
        if form.is_valid():
            membership = form.save(commit=False)
            membership.role = Membership.ROLE_SUB_ADMIN
            membership.save()
            messages.success(request, 'Sous-admin nommé avec ses droits.')
    return redirect('communities:manage', slug=community.slug)


@login_required
def manage_demote(request, slug, user_id):
    community = get_object_or_404(Community, slug=slug)
    if request.method == 'POST' and _manage_permission(request.user, community, 'manage_subadmins'):
        target = get_object_or_404(User, pk=user_id)
        if target.is_site_admin:
            messages.error(request, 'Un administrateur du site ne peut pas être rétrogradé.')
        else:
            Membership.objects.filter(community=community, user=target).update(
                role=Membership.ROLE_MEMBER,
                can_manage_members=False,
                can_moderate=False,
                can_edit_community=False,
                can_ban_users=False,
                can_launch_calls=False,
            )
            messages.success(request, 'Le membre a été retiré de l’équipe de modération.')
    return redirect('communities:manage', slug=community.slug)


@login_required
def manage_delete(request, slug):
    community = get_object_or_404(Community, slug=slug)
    if request.method == 'POST' and request.user.is_site_admin:
        name = community.name
        community.delete()
        messages.success(request, f'La communauté « {name} » a été supprimée.')
        return redirect('communities:home')
    return redirect('communities:manage', slug=community.slug)


# ---------------------------------------------------------------------------
# Espace admin du site (réservé aux administrateurs du site)
# ---------------------------------------------------------------------------

def admin_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_site_admin:
            messages.error(request, 'Accès réservé aux administrateurs.')
            return redirect('communities:home')
        return view_func(request, *args, **kwargs)
    return _wrapped


@admin_required
def admin_dashboard(request):
    from django.db.models import Count

    registered = User.objects.filter(is_guest=False)
    guests = User.objects.filter(is_guest=True, last_seen__gte=timezone.now() - timedelta(minutes=10))
    users_with_communities = Membership.objects.values('user').distinct().count()
    return render(request, 'communities/admin_dashboard.html', {
        'community_count': Community.objects.count(),
        'member_count': registered.count(),
        'guest_online_count': guests.count(),
        'total_memberships': Membership.objects.count(),
        'banned_count': User.objects.filter(is_banned=True).count(),
        'communities': Community.objects.all(),
        'admins': User.objects.filter(is_site_admin=True),
    })


@admin_required
def admin_community_create(request):
    if request.method == 'POST':
        form = CommunityForm(request.POST)
        if form.is_valid():
            community = form.save(commit=False)
            community.created_by = request.user
            community.save()
            messages.success(request, f'Communauté « {community.name} » créée !')
            return redirect('communities:manage', slug=community.slug)
    else:
        form = CommunityForm()
    return render(request, 'communities/admin_community_form.html', {
        'form': form,
        'title': 'Créer une communauté',
        'submit_label': 'Créer la communauté',
    })


@admin_required
def admin_users(request):
    users = User.objects.filter(is_guest=False).order_by('-is_site_admin', 'username')
    return render(request, 'communities/admin_users.html', {'users': users})


@admin_required
def admin_users_ban(request, user_id):
    if request.method == 'POST':
        target = get_object_or_404(User, pk=user_id)
        if target.is_site_admin:
            messages.error(request, 'Un administrateur ne peut pas être banni.')
        else:
            target.is_banned = True
            target.save()
            messages.success(request, f'{target.username} a été banni.')
    return redirect('communities:admin_users')


@admin_required
def admin_users_unban(request, user_id):
    if request.method == 'POST':
        target = get_object_or_404(User, pk=user_id)
        target.is_banned = False
        target.save()
        messages.success(request, f'{target.username} a été débloqué.')
    return redirect('communities:admin_users')


@admin_required
def admin_guests(request):
    now = timezone.now()
    threshold = now - timedelta(minutes=10)
    User.objects.filter(is_guest=True).filter(
        Q(last_seen__lt=threshold) | Q(last_seen__isnull=True, created_at__lt=threshold)
    ).delete()
    guests = User.objects.filter(is_guest=True, last_seen__gte=threshold)
    return render(request, 'communities/admin_guests.html', {'guests': guests})


@admin_required
def admin_guests_action(request, user_id):
    if request.method == 'POST':
        target = get_object_or_404(User, pk=user_id, is_guest=True)
        action = request.POST.get('action')
        if action == 'ban':
            target.is_banned = True
            target.save()
            messages.success(request, f'{target.username} a été banni.')
        elif action == 'unban':
            target.is_banned = False
            target.save()
            messages.success(request, f'{target.username} a été débloqué.')
        elif action == 'delete':
            target.delete()
            messages.success(request, 'Compte invité supprimé.')
    return redirect('communities:admin_guests')


@admin_required
def admin_admins(request):
    admins = list(User.objects.filter(is_site_admin=True).order_by('username'))
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'promote':
            username = request.POST.get('username', '').strip()
            user = User.objects.filter(username__iexact=username, is_guest=False).first()
            if not user:
                messages.error(request, f'Aucun utilisateur inscrit « {username} ».')
            elif len(admins) >= 4:
                messages.error(request, 'Le site ne peut avoir que 4 administrateurs maximum.')
            elif user.is_site_admin:
                messages.info(request, 'Cet utilisateur est déjà administrateur.')
            else:
                user.is_site_admin = True
                user.is_staff = True
                user.save()
                messages.success(request, f'{user.username} est maintenant administrateur.')
        elif action == 'create':
            if len(admins) >= 4:
                messages.error(request, 'Le site ne peut avoir que 4 administrateurs maximum.')
            else:
                username = request.POST.get('username', '').strip()
                password = request.POST.get('password', '')
                if not username or not password:
                    messages.error(request, 'Pseudo et mot de passe obligatoires.')
                elif User.objects.filter(username__iexact=username).exists():
                    messages.error(request, 'Ce pseudo existe déjà.')
                else:
                    user = User(username=username)
                    user.set_password(password)
                    user.is_site_admin = True
                    user.is_staff = True
                    user.save()
                    messages.success(request, f'Administrateur « {username} » créé.')
        elif action == 'demote':
            target = get_object_or_404(User, pk=request.POST.get('user_id'))
            if target == request.user:
                messages.error(request, 'Tu ne peux pas te retirer toi-même.')
            elif len(admins) <= 1:
                messages.error(request, 'Impossible de retirer le dernier administrateur.')
            else:
                target.is_site_admin = False
                target.is_staff = False
                target.save()
                messages.success(request, f'{target.username} n’est plus administrateur.')
        return redirect('communities:admin_admins')
    return render(request, 'communities/admin_admins.html', {'admins': admins})