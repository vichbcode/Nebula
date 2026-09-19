"""Modèles communautés, memberships, messages."""

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Community(models.Model):
    name = models.CharField('Nom', max_length=120, unique=True)
    slug = models.SlugField(max_length=130, unique=True, allow_unicode=True)
    description = models.TextField('Description', blank=True)
    guests_allowed = models.BooleanField(
        'Accès invités autorisé',
        default=False,
        help_text='Si activé, les comptes invités peuvent accéder à cette communauté.',
    )
    is_support = models.BooleanField(
        'Communauté d’assistance',
        default=False,
        help_text='Communauté spéciale où les invités et inscrits contactent les administrateurs.',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='Créée par',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Créée le')

    class Meta:
        ordering = ['name']
        verbose_name = 'Communauté'
        verbose_name_plural = 'Communautés'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name, allow_unicode=True) or 'communaute'
            slug = base
            n = 2
            while Community.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @classmethod
    def base_community(cls):
        try:
            return cls.objects.filter(guests_allowed=True).first()
        except cls.DoesNotExist:
            return None

    def user_role(self, user):
        if not user.is_authenticated:
            return None
        if user.is_site_admin:
            return 'admin'
        try:
            m = Membership.objects.get(user=user, community=self)
            return m.role
        except Membership.DoesNotExist:
            return None

    def user_membership(self, user):
        if not user.is_authenticated:
            return None
        return Membership.objects.filter(user=user, community=self).first()

    def member_count(self):
        return self.memberships.count()

    def __str__(self):
        return self.name


class CommunityCall(models.Model):
    CALL_VOICE = 'voice'
    CALL_VIDEO = 'video'
    CALL_CHOICES = [
        (CALL_VOICE, 'Appel vocal'),
        (CALL_VIDEO, 'Appel vidéo'),
    ]

    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name='calls',
        verbose_name='Communauté',
    )
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='started_calls',
        verbose_name='Lancé par',
    )
    call_type = models.CharField('Type', max_length=10, choices=CALL_CHOICES, default=CALL_VOICE)
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='Lancé le')

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'Appel en cours'
        verbose_name_plural = 'Appels en cours'

    def __str__(self):
        return f'{self.community} — {self.get_call_type_display()} ({self.started_by})'


class CallSignal(models.Model):
    """Message de signalisation WebRTC d’un appel en cours."""

    KIND_CHOICES = [
        ('join', 'Rejoint'),
        ('offer', 'Offre'),
        ('answer', 'Réponse'),
        ('ice', 'Candidat ICE'),
        ('bye', 'Départ'),
    ]

    call = models.ForeignKey(
        CommunityCall,
        on_delete=models.CASCADE,
        related_name='signals',
        verbose_name='Appel',
    )
    sender = models.CharField('Émetteur', max_length=64)
    target = models.CharField('Destinataire', max_length=64, blank=True)
    kind = models.CharField('Type', max_length=10, choices=KIND_CHOICES)
    data = models.TextField('Données', blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Envoyé le')

    class Meta:
        ordering = ['id']
        verbose_name = 'Signal d’appel'
        verbose_name_plural = 'Signaux d’appel'

    def __str__(self):
        return f'{self.call} — {self.kind} ({self.sender})'


class Membership(models.Model):
    ROLE_MEMBER = 'member'
    ROLE_SUB_ADMIN = 'sub_admin'
    ROLE_CHOICES = [
        (ROLE_MEMBER, 'Membre'),
        (ROLE_SUB_ADMIN, 'Sous-admin'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    role = models.CharField('Rôle', max_length=15, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    can_manage_members = models.BooleanField('Gérer les membres', default=False)
    can_moderate = models.BooleanField('Modérer les messages', default=False)
    can_edit_community = models.BooleanField('Modifier la communauté', default=False)
    can_ban_users = models.BooleanField('Bannir des utilisateurs', default=False)
    can_launch_calls = models.BooleanField('Lancer les appels', default=False)
    joined_at = models.DateTimeField(auto_now_add=True, verbose_name='Rejoint le')

    class Meta:
        unique_together = ('user', 'community')
        verbose_name = 'Adhésion'
        verbose_name_plural = 'Adhésions'

    def __str__(self):
        return f'{self.user} → {self.community} ({self.get_role_display()})'


class Message(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='messages',
    )
    text = models.TextField('Message', max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Envoyé le')

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'

    def __str__(self):
        return f'{self.author}: {self.text[:50]}'


class SupportThread(models.Model):
    STATUS_OPEN = 'open'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Ouverte'),
        (STATUS_CLOSED, 'Fermée'),
    ]

    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name='support_threads',
        verbose_name='Communauté',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_threads',
        verbose_name='Demandeur',
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='handled_support_threads',
        verbose_name='Admin choisi',
    )
    status = models.CharField(
        'Statut', max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN
    )
    deleted = models.BooleanField('Supprimé', default=False)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='Supprimé par',
    )
    deleted_at = models.DateTimeField('Supprimé le', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Créé le')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Mis à jour le')

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Demande d’assistance'
        verbose_name_plural = 'Demandes d’assistance'

    def last_message(self):
        return self.messages.last()

    def unread_count_for(self, viewer):
        """Messages non lus destinés au viewer (l’autre partie)."""
        if viewer == self.user:
            return self.messages.filter(author=self.admin, is_read=False).count()
        return self.messages.filter(author=self.user, is_read=False).count()

    def __str__(self):
        return f'{self.user} → {self.admin or "tout admin"} ({self.community})'


class SupportMessage(models.Model):
    thread = models.ForeignKey(
        SupportThread,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name='Discussion',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='support_sent_messages',
        verbose_name='Auteur',
    )
    text = models.TextField('Message', max_length=4000)
    is_read = models.BooleanField(
        'Lu par le destinataire',
        default=False,
        help_text='Marqué lu quand l’autre partie ouvre la conversation.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Envoyé le')

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Message d’assistance'
        verbose_name_plural = 'Messages d’assistance'

    def __str__(self):
        return f'{self.author}: {self.text[:50]}'