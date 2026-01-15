"""
Audit Engine URLs
=================
URL patterns for the audit engine.
"""

from django.urls import path

from . import views

app_name = 'audit_engine'

urlpatterns = [
    # Audit management
    path('start/', views.start_audit, name='start_audit'),
    path('upload/', views.upload_reports, name='upload_reports'),
    path('<int:audit_id>/status/', views.audit_status, name='audit_status'),
    path('<int:audit_id>/status/api/', views.audit_status_api, name='audit_status_api'),
    path('<int:audit_id>/results/', views.audit_results, name='audit_results'),
    path('history/', views.audit_history, name='audit_history'),
    
    # Cases
    path('case/<int:case_id>/', views.case_detail, name='case_detail'),
    path('case/<int:case_id>/download/', views.download_case, name='download_case'),
]
