"""Données initiales : administrateur du site + communauté de base."""

from django.db import migrations
from django.contrib.auth.hashers import make_password


def seed(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    Community = apps.get_model('communities', 'Community')
    Membership = apps.get_model('communities', 'Membership')

    admin, created = User.objects.get_or_create(
        username='Gestionnaire',
        defaults={
            'is_staff': True,
            'is_superuser': False,
            'is_site_admin': True,
            'is_active': True,
        },
    )
    if created:
        admin.password = make_password('Gestionnaire95@#')
        admin.save()

    base, created = Community.objects.get_or_create(
        name='Communauté de Base',
        defaults={
            'slug': 'communaute-de-base',
            'description': (
                'La communauté de départ ! Tout le monde y a sa place, '
                'guests comme membres. Ici on discute, on rigole et on '
                's’entraide. Rejoins-nous !'
            ),
            'guests_allowed': True,
            'call_type': 'none',
            'created_by': admin,
        },
    )

    if not Membership.objects.filter(user=admin, community=base).exists():
        Membership.objects.create(user=admin, community=base, role='member')


def unseed(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    Community = apps.get_model('communities', 'Community')
    User.objects.filter(username='Gestionnaire').delete()
    Community.objects.filter(name='Communauté de Base').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('communities', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]