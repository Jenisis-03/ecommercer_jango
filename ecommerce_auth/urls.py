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
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('accounts/', include('accounts.urls')),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('privacy/', views.privacy, name='privacy'),
    path('terms/', views.terms, name='terms'),
    path('faq/', views.faq, name='faq'),
    path('product/<int:product_id>/', views.product_detail, name='product_detail'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('user-signup/', views.user_signup, name='user_signup'),
    path('vendor-signup/', views.vendor_signup, name='vendor_signup'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
    path('vendor-dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('checkout/process/', views.process_checkout, name='process_checkout'),
    path('order-confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
    path('order-history/', views.order_history, name='order_history'),
    path('add-product/', views.add_product, name='add_product'),
    path('edit-product/<int:pk>/', views.edit_product, name='edit_product'),
    path('delete-product/<int:pk>/', views.delete_product, name='delete_product'),
    path('search/', views.search_products, name='search_products'),
    path('rate-product/<int:product_id>/', views.rate_product, name='rate_product'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('get-subcategories/<int:category_id>/', views.get_subcategories, name='get_subcategories'),
    path('debug-categories/', views.debug_categories, name='debug_categories'),
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin-add-user/', views.admin_add_user, name='admin_add_user'),
    path('admin-edit-user/<int:user_id>/', views.admin_edit_user, name='admin_edit_user'),
    path('admin-delete-user/<int:user_id>/', views.admin_delete_user, name='admin_delete_user'),
    path('admin-add-vendor/', views.admin_add_vendor, name='admin_add_vendor'),
    path('admin-edit-vendor/<int:vendor_id>/', views.admin_edit_vendor, name='admin_edit_vendor'),
    path('admin-delete-vendor/<int:vendor_id>/', views.admin_delete_vendor, name='admin_delete_vendor'),
    path('admin-add-product/', views.admin_add_product, name='admin_add_product'),
    path('admin-edit-product/<int:product_id>/', views.admin_edit_product, name='admin_edit_product'),
    path('admin-delete-product/<int:product_id>/', views.admin_delete_product, name='admin_delete_product'),
    path('check-stock/<int:product_id>/', views.check_stock, name='check_stock'),
    path('category/<int:category_id>/', views.category_products, name='category_products_by_category'),
    path('category/<int:category_id>/<int:subcategory_id>/', views.category_products, name='category_products'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/remove/<int:item_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('addresses/', views.address_list, name='address_list'),
    path('addresses/add/', views.add_address, name='add_address'),
    path('addresses/<int:address_id>/edit/', views.edit_address, name='edit_address'),
    path('addresses/<int:address_id>/delete/', views.delete_address, name='delete_address'),
    path('payment-methods/', views.payment_method_list, name='payment_method_list'),
    path('payment-methods/add/', views.add_payment_method, name='add_payment_method'),
    path('payment-methods/<int:payment_id>/delete/', views.delete_payment_method, name='delete_payment_method'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('settings/', views.settings_view, name='settings'),
    path('settings/notifications/', views.notification_settings, name='notification_settings'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/track/', views.track_order, name='track_order'),
    path('orders/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
