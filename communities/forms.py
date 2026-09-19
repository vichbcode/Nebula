"""Formulaires des communautés."""

from django import forms
from django.contrib.auth import get_user_model

from .models import Community, Membership, Message

User = get_user_model()


class CommunityForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = ('name', 'description', 'guests_allowed')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Nom de la communauté',
                'autocomplete': 'off',
            }),
            'description': forms.Textarea(attrs={
                'class': 'input textarea',
                'placeholder': 'Description… (optionnel)',
                'rows': 4,
            }),
            'guests_allowed': forms.CheckboxInput(attrs={'class': 'switch'}),
        }


class CommunityEditForm(forms.ModelForm):
    """Édition nom + description uniquement (ne touche pas l’appel ni les invités)."""

    class Meta:
        model = Community
        fields = ('name', 'description')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'input',
                'placeholder': 'Nom de la communauté',
                'autocomplete': 'off',
            }),
            'description': forms.Textarea(attrs={
                'class': 'input textarea',
                'placeholder': 'Description… (optionnel)',
                'rows': 4,
            }),
        }


class GuestAccessForm(forms.ModelForm):
    class Meta:
        model = Community
        fields = ('guests_allowed',)
        widgets = {
            'guests_allowed': forms.CheckboxInput(attrs={'class': 'switch'}),
        }


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ('text',)
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'input textarea',
                'placeholder': 'Écris un message…',
                'rows': 2,
                'maxlength': 4000,
            }),
        }


class SubAdminRightsForm(forms.ModelForm):
    class Meta:
        model = Membership
        fields = ('can_manage_members', 'can_moderate', 'can_edit_community', 'can_ban_users', 'can_launch_calls')
        widgets = {
            'can_manage_members': forms.CheckboxInput(attrs={'class': 'switch small'}),
            'can_moderate': forms.CheckboxInput(attrs={'class': 'switch small'}),
            'can_edit_community': forms.CheckboxInput(attrs={'class': 'switch small'}),
            'can_ban_users': forms.CheckboxInput(attrs={'class': 'switch small'}),
            'can_launch_calls': forms.CheckboxInput(attrs={'class': 'switch small'}),
        }


class SupportStartForm(forms.Form):
    """Choix de l’admin + premier message pour ouvrir une discussion d’assistance."""

    admin = forms.ModelChoiceField(
        queryset=User.objects.filter(is_site_admin=True).order_by('username'),
        label='Choisis l’administrateur',
        widget=forms.Select(attrs={'class': 'input', 'data-admin-picker': 'true'}),
    )
    text = forms.CharField(
        label='Ton message',
        max_length=4000,
        widget=forms.Textarea(attrs={
            'class': 'input textarea',
            'placeholder': 'Décris ton problème ou votre question…',
            'rows': 3,
        }),
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields['admin'].queryset = (
                self.fields['admin'].queryset.exclude(pk=user.pk)
            )
            if self.fields['admin'].queryset.count() == 1:
                self.fields['admin'].initial = self.fields['admin'].queryset.first()


class SupportReplyForm(forms.Form):
    text = forms.CharField(
        max_length=4000,
        widget=forms.Textarea(attrs={
            'class': 'input textarea',
            'placeholder': 'Réponds…',
            'rows': 2,
            'maxlength': 4000,
        }),
    )