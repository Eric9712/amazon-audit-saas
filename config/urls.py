"""
URL Configuration for Amazon Audit SaaS
========================================
Main URL routing for the entire application.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.views import home


# Admin site customization
admin.site.site_header = "Amazon Audit Administration"
admin.site.site_title = "Amazon Audit Admin"
admin.site.index_title = "Bienvenue dans l'administration Amazon Audit"


urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Admin Console (Custom Dashboard)
    path('console/', include('admin_console.urls', namespace='admin_console')),
    
    # Authentication (django-allauth)
    path('accounts/', include('allauth.urls')),
    
    # Custom accounts app
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    
    # Dashboard (main app)
    path('dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    
    # Amazon Integration API
    path('api/amazon/', include('apps.amazon_integration.urls', namespace='amazon_integration')),
    
    # Audit Engine API
    path('api/audit/', include('apps.audit_engine.urls', namespace='audit_engine')),
    
    # Payments (Stripe)
    path('payments/', include('apps.payments.urls', namespace='payments')),
    
    # Messaging
    path('messagerie/', include('apps.messaging.urls', namespace='messaging')),
    
    # Static pages (FAQ, Terms, Privacy, etc.)
    path('', include('apps.pages.urls', namespace='pages')),
    
    # Homepage (redirects to dashboard if authenticated)
    path('', home, name='home'),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Debug toolbar
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
