"""
Django system checks for production safety.

These checks ensure development tools are not accidentally enabled in production.
Run with: python manage.py check --deploy
"""

from django.core.checks import Warning, Error, register
from django.conf import settings
import os


@register()
def check_development_tools_in_production(app_configs, **kwargs):
    """
    Check if development tools are enabled in production environment.

    This prevents accidentally deploying with Silk, Debug Toolbar, or DEBUG=True.
    """
    warnings = []

    # Determine if this is production
    environment = os.environ.get('ENVIRONMENT', 'production')
    is_production = environment == 'production'

    # Railway environment indicates production ONLY if RAILWAY_ENVIRONMENT is set to a non-empty value
    railway_env = os.environ.get('RAILWAY_ENVIRONMENT', '').strip()
    is_railway = bool(railway_env)  # Empty string = False (local dev), non-empty = True (Railway)

    if is_production or is_railway:
        # Critical: DEBUG should be False in production
        if settings.DEBUG:
            warnings.append(
                Error(
                    'DEBUG=True in production environment!',
                    hint='Set DJANGO_DEBUG=False and ENVIRONMENT=production in environment variables',
                    id='myapp.E001',
                )
            )

        # Check for Silk
        if 'silk' in settings.INSTALLED_APPS:
            warnings.append(
                Error(
                    'Django Silk is enabled in production!',
                    hint='Set ENVIRONMENT=production to disable development tools',
                    id='myapp.E002',
                )
            )

        # Check for Debug Toolbar
        if 'debug_toolbar' in settings.INSTALLED_APPS:
            warnings.append(
                Error(
                    'Django Debug Toolbar is enabled in production!',
                    hint='Set ENVIRONMENT=production to disable development tools',
                    id='myapp.E003',
                )
            )

        # Check if IS_DEVELOPMENT is True in production
        if getattr(settings, 'IS_DEVELOPMENT', False):
            warnings.append(
                Error(
                    'IS_DEVELOPMENT=True in production environment!',
                    hint='Set ENVIRONMENT=production (not "development") in environment variables',
                    id='myapp.E004',
                )
            )

    return warnings


@register()
def check_production_security_settings(app_configs, **kwargs):
    """
    Check that production security settings are properly configured.

    Only runs when DEBUG=False (production mode).
    """
    warnings = []

    if not settings.DEBUG:
        # Check ALLOWED_HOSTS
        if not settings.ALLOWED_HOSTS or settings.ALLOWED_HOSTS == ['*']:
            warnings.append(
                Warning(
                    'ALLOWED_HOSTS not properly configured for production',
                    hint='Set DJANGO_ALLOWED_HOSTS to your domain name(s)',
                    id='myapp.W001',
                )
            )

        # Check SECRET_KEY
        if settings.SECRET_KEY == 'django-insecure-development-secret-key-change-in-production':
            warnings.append(
                Error(
                    'Using default SECRET_KEY in production!',
                    hint='Set DJANGO_SECRET_KEY environment variable to a random string',
                    id='myapp.E005',
                )
            )

        # Check SECURE_SSL_REDIRECT
        if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
            warnings.append(
                Warning(
                    'SECURE_SSL_REDIRECT is not enabled',
                    hint='This setting is auto-enabled when DEBUG=False, verify it is working',
                    id='myapp.W002',
                )
            )

    return warnings
