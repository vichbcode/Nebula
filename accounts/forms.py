"""Formulaires d’authentification et de gestion du compte."""

import random
import string

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm
from django.core.exceptions import ValidationError

User = get_user_model()


class StyledFormMixin:
    """Applique les classes CSS aux champs pour un rendu uniforme."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.PasswordInput):
                widget.attrs['class'] = 'input'
                widget.attrs['placeholder'] = '••••••••'
            elif isinstance(widget, forms.TextInput):
                widget.attrs['class'] = 'input'
                widget.attrs.setdefault('placeholder', '')


class RegisterForm(StyledFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'placeholder': 'Ton pseudo',
            'class': 'input',
            'autocomplete': 'username',
        })

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if username.startswith('#'):
            raise ValidationError(
                'Les comptes inscrits ne peuvent pas commencer par #. '
                'Utilise plutôt « Compte invité ».'
            )
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Ce pseudo est déjà pris par un autre compte.')
        return username


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(
        label='Pseudo',
        widget=forms.TextInput(attrs={
            'class': 'input',
            'placeholder': 'Ton pseudo',
            'autocomplete': 'username',
        }),
    )
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'input',
            'placeholder': 'Ton mot de passe',
            'autocomplete': 'current-password',
        }),
    )

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if username.startswith('#'):
            raise ValidationError(
                'Ce pseudo correspond à un compte invité. Utilise l’onglet « Invité ».'
            )
        return username

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_banned:
            raise ValidationError('Ce compte a été banni. Contacter un administrateur.')
        if user.is_guest:
            raise ValidationError('Ce pseudo correspond à un compte invité.')


def random_guest_name():
    adjectives = ['Lumineux', 'Cosmique', 'Furtif', 'Électrique', 'Brillant',
                  'Mystique', 'Sauvage', 'Céleste', 'Rapide', 'Néon']
    animals = ['Panda', 'Furet', 'Renard', 'Dauphin', 'Guépard', 'Hibou',
               'Phoenix', 'Loutre', 'Gecko', 'Cheval']
    num = ''.join(random.choices(string.digits, k=4))
    return f'#{random.choice(adjectives)}{random.choice(animals)}{num}'


class GuestForm(StyledFormMixin, forms.Form):
    pseudo = forms.CharField(
        label='Pseudo invité',
        max_length=40,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'input',
            'placeholder': 'Ex : #LumineuxPanda',
            'autocomplete': 'off',
        }),
        help_text='Commence obligatoirement par #. Laisse vide pour en choisir un au hasard.',
    )

    def clean(self):
        cleaned = super().clean()
        pseudo = (cleaned.get('pseudo') or '').strip() or random_guest_name()
        if not pseudo.startswith('#'):
            raise ValidationError('Le pseudo d’un invité doit commencer par #.')
        pseudo = pseudo[:40]
        cleaned['pseudo'] = pseudo
        if User.objects.filter(is_guest=True, username__iexact=pseudo).exists():
            raise ValidationError('Ce pseudo est déjà utilisé par un autre invité connecté.')
        return cleaned


class ProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'input',
            'placeholder': 'Nouveau pseudo',
            'autocomplete': 'off',
        })

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if self.instance.pk and self.instance.is_guest:
            if not username.startswith('#'):
                raise ValidationError('Le pseudo d’un invité doit commencer par #.')
        elif username.startswith('#'):
            raise ValidationError('Les comptes inscrits ne peuvent pas commencer par #.')
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise ValidationError('Ce pseudo est déjà pris par un autre compte.')
        return username


class ChangePasswordForm(StyledFormMixin, PasswordChangeForm):
    old_password = forms.CharField(
        label='Mot de passe actuel',
        widget=forms.PasswordInput(attrs={'class': 'input', 'placeholder': '••••••••'}),
    )
    new_password1 = forms.CharField(
        label='Nouveau mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'input', 'placeholder': '••••••••'}),
    )
    new_password2 = forms.CharField(
        label='Confirme le nouveau mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'input', 'placeholder': '••••••••'}),
    )