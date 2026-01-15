"""
Admin Console - Dashboard Views
Comprehensive admin dashboard with statistics and monitoring.
"""
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()


@staff_member_required
def admin_dashboard(request):
    """Main admin dashboard with all statistics."""
    
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Import models here to avoid circular imports
    from apps.accounts.models import SellerProfile, LoginHistory
    from apps.payments.models import PaymentTransaction
    from apps.audit_engine.models import Audit, ClaimCase
    
    # =========================================================================
    # USER STATISTICS
    # =========================================================================
    total_users = User.objects.count()
    users_today = User.objects.filter(date_joined__date=today).count()
    users_this_week = User.objects.filter(date_joined__date__gte=week_ago).count()
    users_this_month = User.objects.filter(date_joined__date__gte=month_ago).count()
    
    # Users with Amazon connected
    amazon_connected = SellerProfile.objects.filter(is_amazon_connected=True).count()
    
    # =========================================================================
    # LOGIN STATISTICS
    # =========================================================================
    recent_logins = LoginHistory.objects.select_related('user').order_by('-login_time')[:20]
    logins_today = LoginHistory.objects.filter(login_time__date=today).count()
    logins_this_week = LoginHistory.objects.filter(login_time__date__gte=week_ago).count()
    
    # =========================================================================
    # REVENUE STATISTICS
    # =========================================================================
    # Completed transactions
    completed_transactions = PaymentTransaction.objects.filter(
        status=PaymentTransaction.TransactionStatus.COMPLETED
    )
    
    total_revenue = completed_transactions.aggregate(total=Sum('amount'))['total'] or 0
    revenue_today = completed_transactions.filter(
        completed_at__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    revenue_this_week = completed_transactions.filter(
        completed_at__date__gte=week_ago
    ).aggregate(total=Sum('amount'))['total'] or 0
    revenue_this_month = completed_transactions.filter(
        completed_at__date__gte=month_ago
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Pending transactions (awaiting bank transfer validation)
    pending_transactions = PaymentTransaction.objects.filter(
        status=PaymentTransaction.TransactionStatus.PENDING
    ).select_related('seller_profile__user').order_by('-created_at')[:10]
    
    pending_count = PaymentTransaction.objects.filter(
        status=PaymentTransaction.TransactionStatus.PENDING
    ).count()
    
    pending_amount = PaymentTransaction.objects.filter(
        status=PaymentTransaction.TransactionStatus.PENDING
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # All recent transactions
    recent_transactions = PaymentTransaction.objects.select_related(
        'seller_profile__user'
    ).order_by('-created_at')[:15]
    
    # =========================================================================
    # AUDIT STATISTICS
    # =========================================================================
    total_audits = Audit.objects.count()
    audits_in_progress = Audit.objects.filter(status='in_progress').count()
    audits_completed = Audit.objects.filter(status='completed').count()
    
    # Total losses detected
    total_losses = ClaimCase.objects.aggregate(total=Sum('total_value'))['total'] or 0
    
    # =========================================================================
    # CHARTS DATA (Last 30 days)
    # =========================================================================
    # Registrations per day
    registrations_chart = User.objects.filter(
        date_joined__date__gte=month_ago
    ).annotate(
        day=TruncDate('date_joined')
    ).values('day').annotate(count=Count('id')).order_by('day')
    
    # Revenue per day
    revenue_chart = completed_transactions.filter(
        completed_at__date__gte=month_ago
    ).annotate(
        day=TruncDate('completed_at')
    ).values('day').annotate(total=Sum('amount')).order_by('day')
    
    # =========================================================================
    # RECENT USERS
    # =========================================================================
    recent_users = User.objects.order_by('-date_joined')[:10]
    
    context = {
        # User stats
        'total_users': total_users,
        'users_today': users_today,
        'users_this_week': users_this_week,
        'users_this_month': users_this_month,
        'amazon_connected': amazon_connected,
        
        # Login stats
        'recent_logins': recent_logins,
        'logins_today': logins_today,
        'logins_this_week': logins_this_week,
        
        # Revenue stats
        'total_revenue': total_revenue,
        'revenue_today': revenue_today,
        'revenue_this_week': revenue_this_week,
        'revenue_this_month': revenue_this_month,
        'pending_transactions': pending_transactions,
        'pending_count': pending_count,
        'pending_amount': pending_amount,
        'recent_transactions': recent_transactions,
        
        # Audit stats
        'total_audits': total_audits,
        'audits_in_progress': audits_in_progress,
        'audits_completed': audits_completed,
        'total_losses': total_losses,
        
        # Charts
        'registrations_chart': list(registrations_chart),
        'revenue_chart': list(revenue_chart),
        
        # Recent users
        'recent_users': recent_users,
    }
    
    return render(request, 'admin_console/dashboard.html', context)


@staff_member_required
def users_list(request):
    """List all users with details."""
    from apps.accounts.models import SellerProfile
    
    users = User.objects.all().order_by('-date_joined')
    
    context = {
        'users': users,
    }
    return render(request, 'admin_console/users_list.html', context)


@staff_member_required
def transactions_list(request):
    """List all transactions with filtering."""
    from apps.payments.models import PaymentTransaction
    
    status_filter = request.GET.get('status', '')
    
    transactions = PaymentTransaction.objects.select_related(
        'seller_profile__user'
    ).order_by('-created_at')
    
    if status_filter:
        transactions = transactions.filter(status=status_filter)
    
    context = {
        'transactions': transactions,
        'status_filter': status_filter,
    }
    return render(request, 'admin_console/transactions_list.html', context)


@staff_member_required
def logins_list(request):
    """List all login history."""
    from apps.accounts.models import LoginHistory
    
    logins = LoginHistory.objects.select_related('user').order_by('-login_time')[:100]
    
    context = {
        'logins': logins,
    }
    return render(request, 'admin_console/logins_list.html', context)
