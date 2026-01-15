"""
Admin Console - URL Configuration
"""
from django.urls import path
from . import views

app_name = 'admin_console'

urlpatterns = [
    path('', views.admin_dashboard, name='dashboard'),
    path('users/', views.users_list, name='users'),
    path('transactions/', views.transactions_list, name='transactions'),
    path('logins/', views.logins_list, name='logins'),
]
