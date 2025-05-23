from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('signout/', views.signout, name='signout'),
    path('vendor/signup/', views.vendor_signup, name='vendor_signup'),
    path('vendor/dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
]