"""
Main Views
==========
Root views for the application.
"""

from django.shortcuts import render, redirect


def home(request):
    """Home page view."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    return render(request, 'home.html')
