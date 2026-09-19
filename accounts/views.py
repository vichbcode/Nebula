"""Vues d’authentification : connexion, inscription, compte invité, paramètres."""

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from communities.models import Community, Membership

from .forms import ChangePasswordForm, GuestForm, LoginForm, ProfileForm, RegisterForm
from .ratelimit import client_ip, ratelimit

User = get_user_model()


def welcome_view(request):
    """Page d’accueil publique (volet de choix : invité / inscription / connexion)."""
    if request.user.is_authenticated:
        return redirect('communities:home')
    login_form = LoginForm()
    guest_form = GuestForm()
    register_form = RegisterForm()
    return render(request, 'accounts/index.html', {
        'login_form': login_form,
        'guest_form': guest_form,
        'register_form': register_form,
    })


@ratelimit('login-ip', 60, window=900)
@ratelimit('login-user', 15, window=900,
           key=lambda r: f'{client_ip(r)}|{r.POST.get("username", "").strip().lower()}')
def login_view(request):
    if request.user.is_authenticated:
        return redirect('communities:home')
    form = GuestForm()
    login_form = LoginForm()
    register_form = RegisterForm()
    if request.method == 'POST':
        login_form = LoginForm(request, data=request.POST)
        if login_form.is_valid():
            user = login_form.get_user()
            login(request, user)
            messages.success(
                request,
                f'Ravi de te revoir, {user.username} !',
            )
            return redirect('communities:home')
    return render(request, 'accounts/index.html', {
        'login_form': login_form,
        'guest_form': form,
        'register_form': register_form,
        'active': 'login',
    })


@ratelimit('register', 10, window=900)
def register_view(request):
    if request.user.is_authenticated:
        return redirect('communities:home')
    login_form = LoginForm()
    guest_form = GuestForm()
    register_form = RegisterForm()
    if request.method == 'POST':
        register_form = RegisterForm(request.POST)
        if register_form.is_valid():
            user = register_form.save()
            user.is_staff = False
            user.save()
            login(request, user)
            messages.success(request, f'Bienvenue, {user.username} ! Ton compte est créé.')
            return redirect('communities:home')
    return render(request, 'accounts/index.html', {
        'login_form': login_form,
        'guest_form': guest_form,
        'register_form': register_form,
        'active': 'register',
    })


@ratelimit('guest', 12, window=900)
def guest_login_view(request):
    """Crée ou continue un compte invité éphémère (pseudo préfixé par #)."""
    if request.user.is_authenticated:
        return redirect('communities:home')
    form = GuestForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            pseudo = form.cleaned_data['pseudo']
            user = User.objects.create(
                username=pseudo,
                is_guest=True,
                is_active=True,
            )
            user.set_unusable_password()
            user.save()
            login(request, user)
            base = Community.base_community()
            if base and not Membership.objects.filter(user=user, community=base).exists():
                Membership.objects.create(user=user, community=base, role='member')
                messages.info(request, f'Bienvenue {pseudo} ! Tu as rejoint {base.name}.')
            else:
                messages.info(request, f'Bienvenue {pseudo} ! Explore les communautés.')
            return redirect('communities:home')
        return render(request, 'accounts/index.html', {
            'login_form': LoginForm(),
            'guest_form': form,
            'register_form': RegisterForm(),
            'active': 'guest',
        })
    return redirect('accounts:login')


@require_POST
def logout_view(request):
    user = request.user
    if user.is_authenticated and user.is_guest:
        user.delete()
        messages.info(request, 'À bientôt ! Ton compte invité a été supprimé.')
    else:
        if user.is_authenticated:
            User.objects.filter(pk=user.pk).update(last_seen=None)
        logout(request)
        messages.info(request, 'Tu es bien déconnecté.')
    return redirect('communities:index')


@login_required
def settings_view(request):
    user = request.user
    profile_form = None
    password_form = None

    if user.is_guest:
        password_form = None
        profile_form = ProfileForm(request.POST or None, instance=user)
        if request.method == 'POST' and 'update_username' in request.POST:
            if profile_form.is_valid():
                old = user.username
                profile_form.save()
                messages.success(request, f'Pseudo modifié : {old} → {user.username}.')
                return redirect('accounts:settings')
    else:
        profile_form = ProfileForm(request.POST or None, instance=user)
        password_form = ChangePasswordForm(user, request.POST or None)
        if request.method == 'POST':
            if 'update_username' in request.POST:
                if profile_form.is_valid():
                    old = user.username
                    profile_form.save()
                    messages.success(request, f'Pseudo modifié : {old} → {user.username}.')
                    return redirect('accounts:settings')
            elif 'update_password' in request.POST:
                if password_form.is_valid():
                    password_form.save()
                    messages.success(request, 'Mot de passe modifié avec succès.')
                    return redirect('accounts:settings')

    return render(request, 'accounts/settings.html', {
        'profile_form': profile_form,
        'password_form': password_form,
    })


@login_required
def delete_account_view(request):
    if request.method == 'POST':
        user = request.user
        if not user.is_guest:
            logout(request)
            user.delete()
            messages.success(request, 'Ton compte a été supprimé. À bientôt !')
        else:
            messages.info(request, 'En tant qu’invité tu peux simplement te déconnecter.')
        return redirect('communities:index')
    return redirect('accounts:settings')