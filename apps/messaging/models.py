"""
Messaging Models
================
Models for internal messaging system.
"""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User


class Conversation(models.Model):
    """
    A conversation/ticket between a user and support.
    """
    
    class Status(models.TextChoices):
        OPEN = 'open', _('Ouvert')
        AWAITING_REPLY = 'awaiting_reply', _('En attente de réponse')
        RESOLVED = 'resolved', _('Résolu')
        CLOSED = 'closed', _('Fermé')
    
    class Category(models.TextChoices):
        GENERAL = 'general', _('Question générale')
        TECHNICAL = 'technical', _('Problème technique')
        BILLING = 'billing', _('Facturation')
        AUDIT = 'audit', _('Question sur un audit')
        OTHER = 'other', _('Autre')
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conversations',
        verbose_name=_('utilisateur')
    )
    subject = models.CharField(_('sujet'), max_length=200)
    category = models.CharField(
        _('catégorie'),
        max_length=20,
        choices=Category.choices,
        default=Category.GENERAL
    )
    status = models.CharField(
        _('statut'),
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN
    )
    
    created_at = models.DateTimeField(_('créé le'), auto_now_add=True)
    updated_at = models.DateTimeField(_('modifié le'), auto_now=True)
    resolved_at = models.DateTimeField(_('résolu le'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('conversation')
        verbose_name_plural = _('conversations')
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"#{self.id} - {self.subject}"
    
    @property
    def unread_count(self):
        """Count unread messages for the user."""
        return self.messages.filter(is_from_support=True, is_read=False).count()
    
    def mark_as_resolved(self):
        """Mark conversation as resolved."""
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at', 'updated_at'])


class Message(models.Model):
    """
    A message within a conversation.
    """
    
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_('conversation')
    )
    content = models.TextField(_('contenu'))
    is_from_support = models.BooleanField(
        _('message du support'),
        default=False,
        help_text=_('True si le message vient du support, False si de l\'utilisateur')
    )
    is_read = models.BooleanField(_('lu'), default=False)
    
    created_at = models.DateTimeField(_('envoyé le'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('message')
        verbose_name_plural = _('messages')
        ordering = ['created_at']
    
    def __str__(self):
        sender = "Support" if self.is_from_support else "Utilisateur"
        return f"{sender}: {self.content[:50]}..."
    
    def mark_as_read(self):
        """Mark message as read."""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
