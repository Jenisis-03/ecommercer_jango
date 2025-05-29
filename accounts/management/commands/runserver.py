from django.core.management.commands.runserver import Command as RunserverCommand
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(RunserverCommand):
    def handle(self, *args, **options):
        if settings.DEBUG:
            # Force HTTP in development
            settings.SECURE_SSL_REDIRECT = False
            settings.SESSION_COOKIE_SECURE = False
            settings.CSRF_COOKIE_SECURE = False
            settings.SECURE_PROXY_SSL_HEADER = None
            settings.SECURE_HSTS_SECONDS = 0
            settings.SECURE_HSTS_INCLUDE_SUBDOMAINS = False
            settings.SECURE_HSTS_PRELOAD = False
            settings.SECURE_BROWSER_XSS_FILTER = False
            settings.SECURE_CONTENT_TYPE_NOSNIFF = False
            settings.X_FRAME_OPTIONS = 'SAMEORIGIN'
            
            # Override the default server settings
            options['insecure'] = True
            options['http_protocol'] = 'http'
            
        super().handle(*args, **options) 