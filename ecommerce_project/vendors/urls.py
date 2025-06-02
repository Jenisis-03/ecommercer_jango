from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('signup/', views.vendor_signup, name='vendor_signup'),
    path('login/', views.vendor_login, name='vendor_login'),
    path('logout/', views.vendor_logout, name='vendor_logout'),
    
    # Password Reset URLs
    path('password-reset/',
         auth_views.PasswordResetView.as_view(template_name='vendors/password_reset.html'),
         name='vendor_password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(template_name='vendors/password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='vendors/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='vendors/password_reset_complete.html'),
         name='password_reset_complete'),
    
    # Email Verification
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='vendor_verify_email'),
    path('email-verification-sent/', views.email_verification_sent, name='vendor_email_verification_sent'),
    path('dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
    path('settings/', views.vendor_settings, name='vendor_settings'),
    path('orders/', views.vendor_orders, name='vendor_orders'),
]