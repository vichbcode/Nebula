"""Données : communauté d’assistance spéciale (invités + inscrits → admins)."""

from django.db import migrations


def seed(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    Community = apps.get_model('communities', 'Community')
    Membership = apps.get_model('communities', 'Membership')

    admin = User.objects.filter(is_site_admin=True).first()
    support, created = Community.objects.get_or_create(
        slug='support',
        defaults={
            'name': 'Solliciter un administrateur',
            'description': (
                'Besoin d’aide, de conseils ou d’un échange avec un administrateur ? '
                'Choisis l’administrateur avec qui tu veux discuter et écris ton message. '
                'Une seule conversation par administrateur.'
            ),
            'guests_allowed': True,
            'is_support': True,
            'created_by': admin,
        },
    )
    if created:
        support.is_support = True
        support.guests_allowed = True
        support.save(update_fields=['is_support', 'guests_allowed'])
    if admin and not Membership.objects.filter(user=admin, community=support).exists():
        Membership.objects.create(user=admin, community=support, role='member')


def unseed(apps, schema_editor):
    Community = apps.get_model('communities', 'Community')
    Community.objects.filter(slug='support').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('communities', '0005_support'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]