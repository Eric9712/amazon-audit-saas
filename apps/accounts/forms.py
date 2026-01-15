"""
Accounts Forms
==============
Forms for user registration, profile updates, etc.
"""

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _

from .models import User, SellerProfile


class CustomUserCreationForm(UserCreationForm):
    """
    Custom user creation form for registration.
    """
    
    email = forms.EmailField(
        label=_('Adresse email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'votre@email.com',
            'autocomplete': 'email',
        })
    )
    first_name = forms.CharField(
        label=_('Prénom'),
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Jean',
        })
    )
    last_name = forms.CharField(
        label=_('Nom'),
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Dupont',
        })
    )
    company_name = forms.CharField(
        label=_('Nom de votre entreprise'),
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ma Boutique Amazon',
        })
    )
    password1 = forms.CharField(
        label=_('Mot de passe'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••',
            'autocomplete': 'new-password',
        }),
    )
    password2 = forms.CharField(
        label=_('Confirmez le mot de passe'),
        strip=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••',
            'autocomplete': 'new-password',
        }),
    )
    accept_terms = forms.BooleanField(
        label=_("J'accepte les conditions d'utilisation et la politique de confidentialité"),
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        })
    )
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'company_name', 'password1', 'password2')
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email'].lower()
        
        if commit:
            user.save()
            # Create seller profile
            SellerProfile.objects.create(user=user)
        
        return user


class CustomUserChangeForm(UserChangeForm):
    """
    Custom user change form for admin.
    """
    
    class Meta:
        model = User
        fields = '__all__'


class UserProfileForm(forms.ModelForm):
    """
    Form for users to update their profile.
    """
    
    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'phone',
            'company_name',
            'email_notifications',
            'preferred_language',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+33 6 12 34 56 78',
            }),
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'email_notifications': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'preferred_language': forms.Select(attrs={
                'class': 'form-select',
            }),
        }


class ChangeEmailForm(forms.Form):
    """
    Form for changing email address.
    """
    
    new_email = forms.EmailField(
        label=_('Nouvelle adresse email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'nouvelle@email.com',
        })
    )
    confirm_email = forms.EmailField(
        label=_('Confirmez l\'adresse email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'nouvelle@email.com',
        })
    )
    current_password = forms.CharField(
        label=_('Mot de passe actuel'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••',
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        new_email = cleaned_data.get('new_email', '').lower()
        confirm_email = cleaned_data.get('confirm_email', '').lower()
        current_password = cleaned_data.get('current_password')
        
        # Check emails match
        if new_email != confirm_email:
            raise forms.ValidationError(
                _('Les adresses email ne correspondent pas.')
            )
        
        # Check email not already in use
        if User.objects.filter(email=new_email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError(
                _('Cette adresse email est déjà utilisée.')
            )
        
        # Verify current password
        if not self.user.check_password(current_password):
            raise forms.ValidationError(
                _('Mot de passe incorrect.')
            )
        
        return cleaned_data


class DeleteAccountForm(forms.Form):
    """
    Form for account deletion confirmation.
    """
    
    confirm_email = forms.EmailField(
        label=_('Confirmez votre email'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'votre@email.com',
        })
    )
    password = forms.CharField(
        label=_('Mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '••••••••',
        })
    )
    confirm_delete = forms.BooleanField(
        label=_('Je comprends que cette action est irréversible et que toutes mes données seront supprimées.'),
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        })
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        confirm_email = cleaned_data.get('confirm_email', '').lower()
        password = cleaned_data.get('password')
        
        if confirm_email != self.user.email:
            raise forms.ValidationError(
                _('L\'adresse email ne correspond pas à votre compte.')
            )
        
        if not self.user.check_password(password):
            raise forms.ValidationError(
                _('Mot de passe incorrect.')
            )
        
        return cleaned_data
