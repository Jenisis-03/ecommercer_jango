from django.conf import settings
from django.http import HttpResponsePermanentRedirect

class DevelopmentSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG:
            # Force HTTP in development
            request.is_secure = lambda: False
            request._is_secure = False
            
            # If request is HTTPS, redirect to HTTP
            if request.is_secure():
                url = request.build_absolute_uri(request.get_full_path())
                url = url.replace('https://', 'http://')
                return HttpResponsePermanentRedirect(url)
                
        return self.get_response(request) 