"""
Dashboard URLs
==============
"""

from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('connect-amazon/', views.connect_amazon, name='connect_amazon'),
    path('audit/<int:audit_id>/status/', views.audit_status, name='audit_status'),
]
