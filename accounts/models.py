"""Modèle utilisateur personnalisé : comptes invités, bannissements, administrateurs du site."""

import re

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

USERNAME_REGEX = re.compile(r'^[\w.@+!#\- ]+$')


def validate_username_global(value):
    if not USERNAME_REGEX.match(value):
        raise ValidationError(
            'Le pseudo ne peut contenir que des lettres, chiffres et les caractères . @ + ! # - _'
        )
    if value != value.strip():
        raise ValidationError('Le pseudo ne peut pas commencer ou finir par un espace.')


class User(AbstractUser):
    """Utilisateur : compte inscrit, invité ou administrateur du site."""

    first_name = None
    last_name = None
    email = None

    is_guest = models.BooleanField(
        default=False,
        verbose_name='Compte invité',
        help_text='Compte invité éphémère créé via « Compte invité ».',
    )
    is_banned = models.BooleanField(
        default=False,
        verbose_name='Banni',
        help_text='Bloque complètement l’accès au site.',
    )
    is_site_admin = models.BooleanField(
        default=False,
        verbose_name='Administrateur du site',
        help_text='Listé parmi les administrateurs du site (4 maximum).',
    )
    last_seen = models.DateTimeField(
        null=True, blank=True, verbose_name='Dernière activité'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Créé le')

    # unique=True est requis par Django (= USERNAME_FIELD), mais une contrainte
    # unique a été retirée en base de données (migration 0002) pour qu’un pseudo
    # invité puisse être réutilisé même s’il est déjà porté par un invité connecté.
    # L’unicité des comptes inscrits reste garantie au niveau des formulaires.
    username = models.CharField(
        'Pseudo',
        max_length=40,
        unique=True,
        validators=[validate_username_global],
    )

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        constraints = [
            models.UniqueConstraint(
                fields=['username'],
                condition=Q(is_guest=False),
                name='accounts_user_username_unique_non_guest',
            ),
        ]

    @property
    def is_online(self):
        return self.last_seen is not None and (
            timezone.now() - self.last_seen
        ).total_seconds() < 10 * 60

    @property
    def display_name(self):
        return self.username

    def touch(self):
        self.last_seen = timezone.now()
        User.objects.filter(pk=self.pk).update(last_seen=timezone.now())

    def __str__(self):
        return self.username