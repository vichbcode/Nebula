"""Supprime la contrainte UNIQUE sur le pseudo pour autoriser les doublons d’invités.

L’unicité des comptes inscrits reste garantie par les formulaires.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE accounts_user DROP CONSTRAINT IF EXISTS accounts_user_username_key;',
            reverse_sql='ALTER TABLE accounts_user ADD CONSTRAINT accounts_user_username_key UNIQUE (username);',
        ),
    ]