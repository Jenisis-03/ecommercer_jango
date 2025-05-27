from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('auth/', views.login_view, name='auth'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup, name='signup'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('vendor/dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('signout/', views.signout, name='signout'),
    path('vendor/signup/', views.vendor_signup, name='vendor_signup'),
    path('vendor/dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    # path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    # path('cart/', views.view_cart, name='view_cart'),
    # path('update-cart/<int:item_id>/', views.update_cart, name='update_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('order-confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
    path('search/', views.search_products, name='search_products'),
    path('orders/history/', views.order_history, name='order_history'),
    path('product/<int:product_id>/check-stock/', views.check_stock, name='check_stock'),
    path('product/<int:product_id>/rate/', views.rate_product, name='rate_product')
]