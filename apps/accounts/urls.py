"""
Accounts URLs
=============
URL patterns for the accounts app.
"""

from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    # Profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('profile/change-email/', views.ChangeEmailView.as_view(), name='change_email'),
    path('profile/delete/', views.DeleteAccountView.as_view(), name='delete_account'),
    
    # Security
    path('security/', views.AccountSecurityView.as_view(), name='security'),
    
    # Subscription
    path('subscription/', views.SubscriptionView.as_view(), name='subscription'),
    
    # Amazon
    path('disconnect-amazon/', views.disconnect_amazon, name='disconnect_amazon'),
]
