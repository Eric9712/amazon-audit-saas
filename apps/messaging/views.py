"""
Messaging Views
===============
Views for the messaging system.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages as django_messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Conversation, Message


@login_required
def inbox(request):
    """Display user's conversations."""
    conversations = Conversation.objects.filter(user=request.user)
    
    # Calculate unread count
    total_unread = sum(c.unread_count for c in conversations)
    
    context = {
        'conversations': conversations,
        'total_unread': total_unread,
    }
    return render(request, 'messaging/inbox.html', context)


@login_required
def conversation_detail(request, conversation_id):
    """Display a conversation and its messages."""
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        user=request.user
    )
    
    # Mark all support messages as read
    conversation.messages.filter(is_from_support=True, is_read=False).update(is_read=True)
    
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                conversation=conversation,
                content=content,
                is_from_support=False
            )
            # Update conversation status
            conversation.status = Conversation.Status.OPEN
            conversation.save(update_fields=['status', 'updated_at'])
            django_messages.success(request, "Votre message a été envoyé.")
            return redirect('messaging:conversation', conversation_id=conversation.id)
        else:
            django_messages.error(request, "Le message ne peut pas être vide.")
    
    context = {
        'conversation': conversation,
        'messages_list': conversation.messages.all(),
    }
    return render(request, 'messaging/conversation.html', context)


@login_required
def new_conversation(request):
    """Create a new conversation."""
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        category = request.POST.get('category', 'general')
        content = request.POST.get('content', '').strip()
        
        if not subject:
            django_messages.error(request, "Le sujet est obligatoire.")
        elif not content:
            django_messages.error(request, "Le message ne peut pas être vide.")
        else:
            # Create conversation
            conversation = Conversation.objects.create(
                user=request.user,
                subject=subject,
                category=category
            )
            
            # Create first message
            Message.objects.create(
                conversation=conversation,
                content=content,
                is_from_support=False
            )
            
            django_messages.success(request, "Votre message a été envoyé. Nous vous répondrons dans les plus brefs délais.")
            return redirect('messaging:conversation', conversation_id=conversation.id)
    
    context = {
        'categories': Conversation.Category.choices,
    }
    return render(request, 'messaging/new_conversation.html', context)


@login_required
def contact(request):
    """Public contact page that redirects to messaging."""
    if request.user.is_authenticated:
        return redirect('messaging:new_conversation')
    return render(request, 'messaging/contact_login_required.html')


@login_required
@require_POST
def close_conversation(request, conversation_id):
    """Close a conversation."""
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        user=request.user
    )
    
    conversation.status = Conversation.Status.CLOSED
    conversation.save(update_fields=['status', 'updated_at'])
    
    django_messages.success(request, "La conversation a été fermée.")
    return redirect('messaging:inbox')


@login_required
def unread_count(request):
    """API endpoint to get unread message count."""
    count = Message.objects.filter(
        conversation__user=request.user,
        is_from_support=True,
        is_read=False
    ).count()
    
    return JsonResponse({'unread_count': count})
