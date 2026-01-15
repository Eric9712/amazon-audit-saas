"""
Messaging URLs
==============
URL patterns for messaging app.
"""

from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('nouveau/', views.new_conversation, name='new_conversation'),
    path('conversation/<int:conversation_id>/', views.conversation_detail, name='conversation'),
    path('conversation/<int:conversation_id>/fermer/', views.close_conversation, name='close_conversation'),
    path('api/unread/', views.unread_count, name='unread_count'),
]
