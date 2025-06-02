from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('users.urls')),  # Change from 'users/' to 'accounts/'
    
    # Vendor URLs
    path('vendors/', include('vendors.urls')),
    
    # Product URLs
    path('products/', include('products.urls')),
    
    # Order URLs
    path('orders/', include('orders.urls')),
    
    # Core URLs
    path('', include('core.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)