"""
Amazon Integration URLs
=======================
URL patterns for Amazon integration.
"""

from django.urls import path

from . import views

app_name = 'amazon_integration'

urlpatterns = [
    # OAuth flow
    path('connect/', views.initiate_amazon_auth, name='initiate_auth'),
    path('callback/', views.oauth_callback, name='oauth_callback'),
    
    # Connection management
    path('status/', views.check_connection_status, name='check_status'),
    path('disconnect/', views.disconnect_amazon, name='disconnect'),
    path('settings/', views.amazon_settings, name='settings'),
]
