"""
URL configuration for ecommerce_auth project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from accounts import views
from django.conf import settings
from django.conf.urls.static import static

app_name = 'ecommerce'

urlpatterns = [
    # Admin routes
    path('admin/', admin.site.urls),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-login/', views.admin_login, name='admin_login'),
    
    # Main pages
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('privacy/', views.privacy, name='privacy'),
    path('terms/', views.terms, name='terms'),
    path('faq/', views.faq, name='faq'),
    
    # Authentication routes
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('user-signup/', views.user_signup, name='user_signup'),
    path('vendor-signup/', views.vendor_signup, name='vendor_signup'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    
    # User dashboard routes
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:item_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    
    # Product routes
    path('products/', views.product_list, name='product_list'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('search/', views.search_products, name='search_products'),
    path('category/<int:category_id>/', views.category_products, name='category_products'),
    path('subcategory/<int:subcategory_id>/', views.subcategory_products, name='subcategory_products'),
    path('rate-product/<int:product_id>/', views.rate_product, name='rate_product'),
    
    # Cart routes
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    
    # Checkout and order routes
    path('checkout/', views.checkout, name='checkout'),
    path('payment/<int:order_id>/', views.payment, name='payment'),
    path('order-confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
    path('order-history/', views.order_list, name='order_history'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('track-order/<int:order_id>/', views.track_order, name='track_order'),
    
    # Vendor routes
    path('vendor-dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('vendor/add-product/', views.add_product, name='add_product'),
    path('vendor/edit-product/<int:pk>/', views.edit_product, name='edit_product'),
    path('vendor/delete-product/<int:pk>/', views.delete_product, name='delete_product'),
    
    # Address management
    path('addresses/', views.address_list, name='address_list'),
    path('address/add/', views.add_address, name='add_address'),
    path('address/edit/<int:address_id>/', views.edit_address, name='edit_address'),
    path('address/delete/<int:address_id>/', views.delete_address, name='delete_address'),
    
    # Payment routes
    path('create-payment-intent/', views.create_payment_intent, name='create_payment_intent'),
    path('stripe-webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('payment-method/add/', views.add_payment_method, name='add_payment_method'),
    path('payment-method/delete/<int:payment_id>/', views.delete_payment_method, name='delete_payment_method'),
    
    # API routes
    path('get-subcategories/<int:category_id>/', views.get_subcategories, name='get_subcategories'),
    path('check-stock/<int:product_id>/', views.check_stock, name='check_stock'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
