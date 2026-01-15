"""
Accounts Views
==============
Views for account management.
"""

import logging

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, UpdateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import User, SellerProfile, LoginHistory
from .forms import UserProfileForm, ChangeEmailForm, DeleteAccountForm

logger = logging.getLogger(__name__)


class ProfileView(LoginRequiredMixin, TemplateView):
    """
    User profile overview page.
    """
    template_name = 'accounts/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get or create seller profile
        seller_profile, created = SellerProfile.objects.get_or_create(user=user)
        
        context['user'] = user
        context['seller_profile'] = seller_profile
        context['recent_logins'] = LoginHistory.objects.filter(user=user)[:5]
        
        return context


class ProfileEditView(LoginRequiredMixin, UpdateView):
    """
    Edit user profile.
    """
    model = User
    form_class = UserProfileForm
    template_name = 'accounts/profile_edit.html'
    success_url = reverse_lazy('accounts:profile')
    
    def get_object(self, queryset=None):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(
            self.request,
            'Votre profil a été mis à jour avec succès.'
        )
        return super().form_valid(form)


class ChangeEmailView(LoginRequiredMixin, FormView):
    """
    Change email address.
    """
    template_name = 'accounts/change_email.html'
    form_class = ChangeEmailForm
    success_url = reverse_lazy('accounts:profile')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        user = self.request.user
        new_email = form.cleaned_data['new_email'].lower()
        
        # Update email
        user.email = new_email
        user.save(update_fields=['email'])
        
        # Log the change
        logger.info(f"User {user.pk} changed email to {new_email}")
        
        messages.success(
            self.request,
            'Votre adresse email a été modifiée avec succès.'
        )
        return super().form_valid(form)


class DeleteAccountView(LoginRequiredMixin, FormView):
    """
    Delete user account.
    """
    template_name = 'accounts/delete_account.html'
    form_class = DeleteAccountForm
    success_url = reverse_lazy('home')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        user = self.request.user
        email = user.email
        
        # Log the deletion
        logger.warning(f"User {user.pk} ({email}) deleted their account")
        
        # Logout and delete
        logout(self.request)
        user.delete()
        
        messages.success(
            self.request,
            'Votre compte a été supprimé avec succès. Nous sommes désolés de vous voir partir.'
        )
        return super().form_valid(form)


class AccountSecurityView(LoginRequiredMixin, TemplateView):
    """
    Account security settings page.
    """
    template_name = 'accounts/security.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context['login_history'] = LoginHistory.objects.filter(user=user)[:20]
        context['api_keys'] = user.api_keys.filter(is_active=True)
        
        return context


class SubscriptionView(LoginRequiredMixin, TemplateView):
    """
    Subscription management page.
    """
    template_name = 'accounts/subscription.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        seller_profile, created = SellerProfile.objects.get_or_create(user=user)
        
        context['seller_profile'] = seller_profile
        context['credit_transactions'] = seller_profile.credit_transactions.all()[:10]
        
        return context


@login_required
def disconnect_amazon(request):
    """
    Disconnect Amazon account.
    """
    if request.method == 'POST':
        user = request.user
        
        if hasattr(user, 'seller_profile'):
            user.seller_profile.disconnect_amazon()
            
            # Also delete stored credentials
            from apps.amazon_integration.models import AmazonCredentials
            AmazonCredentials.objects.filter(seller_profile=user.seller_profile).delete()
            
            logger.info(f"User {user.pk} disconnected their Amazon account")
            
            messages.success(
                request,
                'Votre compte Amazon a été déconnecté avec succès.'
            )
        
        return redirect('accounts:profile')
    
    return render(request, 'accounts/disconnect_amazon_confirm.html')
