"""
Pages URLs
==========
URL patterns for static pages.
"""

from django.urls import path
from . import views

app_name = 'pages'

urlpatterns = [
    path('comment-ca-marche/', views.how_it_works, name='how_it_works'),
    path('tarifs/', views.pricing, name='pricing'),
    path('faq/', views.faq, name='faq'),
    path('conditions-utilisation/', views.terms, name='terms'),
    path('politique-confidentialite/', views.privacy, name='privacy'),
]
