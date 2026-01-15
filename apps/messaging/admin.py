"""
Messaging Admin
===============
Admin configuration for messaging models.
"""

from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 1
    readonly_fields = ['created_at', 'is_read']
    fields = ['content', 'is_from_support', 'is_read', 'created_at']


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'subject', 'user', 'category', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['subject', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']
    inlines = [MessageInline]
    
    fieldsets = (
        (None, {
            'fields': ('user', 'subject', 'category', 'status')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at', 'resolved_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'is_from_support', 'is_read', 'created_at']
    list_filter = ['is_from_support', 'is_read', 'created_at']
    search_fields = ['content', 'conversation__subject']
    readonly_fields = ['created_at']
