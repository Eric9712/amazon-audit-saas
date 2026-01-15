"""
Accounts Serializers
====================
DRF serializers for API endpoints.
"""

from rest_framework import serializers

from .models import User, SellerProfile, CreditTransaction


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model.
    """
    
    display_name = serializers.CharField(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'first_name',
            'last_name',
            'display_name',
            'company_name',
            'phone',
            'email_notifications',
            'preferred_language',
            'date_joined',
        ]
        read_only_fields = ['id', 'email', 'date_joined', 'display_name']


class SellerProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for SellerProfile model.
    """
    
    user = UserSerializer(read_only=True)
    is_amazon_connected = serializers.BooleanField(read_only=True)
    has_active_subscription = serializers.BooleanField(read_only=True)
    subscription_tier_display = serializers.CharField(
        source='get_subscription_tier_display',
        read_only=True
    )
    
    class Meta:
        model = SellerProfile
        fields = [
            'id',
            'user',
            'amazon_seller_id',
            'amazon_marketplace_ids',
            'amazon_connected_at',
            'is_amazon_connected',
            'subscription_tier',
            'subscription_tier_display',
            'has_active_subscription',
            'subscription_started_at',
            'subscription_ends_at',
            'credits_balance',
            'total_audits_run',
            'total_claims_generated',
            'total_estimated_recovery',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'amazon_seller_id',
            'amazon_marketplace_ids',
            'amazon_connected_at',
            'is_amazon_connected',
            'has_active_subscription',
            'subscription_started_at',
            'subscription_ends_at',
            'credits_balance',
            'total_audits_run',
            'total_claims_generated',
            'total_estimated_recovery',
            'created_at',
        ]


class CreditTransactionSerializer(serializers.ModelSerializer):
    """
    Serializer for CreditTransaction model.
    """
    
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display',
        read_only=True
    )
    
    class Meta:
        model = CreditTransaction
        fields = [
            'id',
            'amount',
            'transaction_type',
            'transaction_type_display',
            'description',
            'reference',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile via API.
    """
    
    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'company_name',
            'phone',
            'email_notifications',
            'preferred_language',
        ]
    
    def validate_phone(self, value):
        """Validate phone number format."""
        if value:
            # Remove spaces and check format
            cleaned = value.replace(' ', '').replace('-', '')
            if not cleaned.replace('+', '').isdigit():
                raise serializers.ValidationError(
                    "Le numéro de téléphone contient des caractères invalides."
                )
        return value
