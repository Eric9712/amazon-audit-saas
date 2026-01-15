"""
Pages Views
============
Static pages views.
"""

from django.shortcuts import render


def how_it_works(request):
    """How it works page."""
    return render(request, 'pages/how_it_works.html')


def pricing(request):
    """Pricing page."""
    return render(request, 'pages/pricing.html')


def faq(request):
    """FAQ page."""
    return render(request, 'pages/faq.html')


def terms(request):
    """Terms of service page."""
    return render(request, 'pages/terms.html')


def privacy(request):
    """Privacy policy page."""
    return render(request, 'pages/privacy.html')
