"""Middleware de sécurité : en-têtes applicatifs (CSP, Permissions-Policy)."""

from django.conf import settings


class SecurityHeadersMiddleware:
    """Pose les en-têtes de sécurité manquants (CSP, Permissions-Policy…)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        policy = getattr(settings, 'CSP_POLICY', '')
        if policy:
            header = (
                'Content-Security-Policy-Report-Only'
                if getattr(settings, 'CSP_REPORT_ONLY', False)
                else 'Content-Security-Policy'
            )
            response[header] = policy
        response.setdefault(
            'Permissions-Policy',
            'camera=(self), microphone=(self), display-capture=(self), '
            'geolocation=(), payment=(), usb=(), interest-cohort=()',
        )
        return response