"""
Payments URLs
=============
"""

from django.urls import path

from . import views
from . import webhooks

app_name = 'payments'

urlpatterns = [
    path('pricing/', views.pricing, name='pricing'),
    path('buy/<int:package_id>/', views.buy_credits, name='buy_credits'),
    path('success/', views.payment_success, name='success'),
    path('history/', views.payment_history, name='history'),
    path('credits/history/', views.credits_history, name='credits_history'),
    path('simulate/<int:package_id>/', views.simulate_payment, name='simulate_payment'),
    
    # Webhooks
    path('webhooks/stripe/', webhooks.stripe_webhook, name='stripe_webhook'),
]
