"""
WSGI config for ecommerce_auth project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path
from django.core.wsgi import get_wsgi_application
from django.conf import settings

# Add the project directory to the Python path
project_path = Path(__file__).resolve().parent.parent
sys.path.append(str(project_path))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce_auth.settings')

# Initialize Django ASGI application early to ensure the app is loaded
# before any other imports
django_application = get_wsgi_application()

def force_http(application):
    def wrapper(environ, start_response):
        if settings.DEBUG:
            environ['wsgi.url_scheme'] = 'http'
            environ['HTTP_X_FORWARDED_PROTO'] = 'http'
        return application(environ, start_response)
    return wrapper

def application(environ, start_response):
    """
    WSGI application that handles the request.
    """
    # Set environment variables
    if 'HTTP_X_FORWARDED_PROTO' in environ:
        os.environ['HTTPS'] = 'on'
    
    return force_http(django_application)(environ, start_response)
