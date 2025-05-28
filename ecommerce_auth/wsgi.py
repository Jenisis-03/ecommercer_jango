"""
WSGI config for ecommerce_auth project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys
from pathlib import Path

# Add the project directory to the Python path
project_path = Path(__file__).resolve().parent.parent
sys.path.append(str(project_path))

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce_auth.settings')

# Initialize Django ASGI application early to ensure the app is loaded
# before any other imports
django_application = get_wsgi_application()

def application(environ, start_response):
    """
    WSGI application that handles the request.
    """
    # Set environment variables
    if 'HTTP_X_FORWARDED_PROTO' in environ:
        os.environ['HTTPS'] = 'on'
    
    return django_application(environ, start_response)
