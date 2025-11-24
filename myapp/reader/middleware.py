"""
Middleware for reader app.
"""
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin


class URLLanguageMiddleware(MiddlewareMixin):
    """
    Middleware to activate language based on URL parameter.

    Extracts language_code from URL kwargs and activates it for Django's
    translation system. This allows URL-based language switching like:
    /en/, /de/, /zh-hans/, etc.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Activate language from URL before view is called.
        """
        language_code = view_kwargs.get('language_code')

        if language_code:
            # Activate the language for this request
            translation.activate(language_code)
            request.LANGUAGE_CODE = language_code

        return None
