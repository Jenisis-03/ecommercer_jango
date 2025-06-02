# users/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_protect
from django.core.cache import cache
from .forms import UserSignUpForm, UserLoginForm
from orders.models import Order
from core.models import Cart

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def check_login_attempts(request):
    client_ip = get_client_ip(request)
    attempts_key = f'login_attempts_{client_ip}'
    attempts = cache.get(attempts_key, 0)
    
    if attempts >= 5:
        return False
    
    cache.set(attempts_key, attempts + 1, 300)  # 5 minutes timeout
    return True

@csrf_protect
def user_signup(request):
    if request.method == 'POST':
        form = UserSignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_vendor = False
            user.save()
            auth_login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('user_dashboard')
    else:
        form = UserSignUpForm()
    return render(request, 'users/signup.html', {'form': form})

@csrf_protect
def user_login(request):
    if request.method == 'POST':
        if not check_login_attempts(request):
            messages.error(request, 'Too many login attempts. Please try again later.')
            return redirect('user_login')
            
        form = UserLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_vendor:
                auth_login(request, user)
                # Reset login attempts on successful login
                client_ip = get_client_ip(request)
                cache.delete(f'login_attempts_{client_ip}')
                messages.success(request, 'Welcome back!')
                return redirect('user_dashboard')
            else:
                messages.error(request, 'This is a customer login. Vendors please use the vendor login.')
        messages.error(request, 'Invalid email or password.')
    else:
        form = UserLoginForm()
    return render(request, 'users/login.html', {'form': form})

@login_required
@csrf_protect
def edit_profile(request):
    if request.method == 'POST':
        user = request.user
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        try:
            # Validate email
            validate_email(email)
            
            # Update basic info
            user.name = name
            user.email = email
            user.phone = phone
            user.address = address
            
            # Handle password change
            if new_password:
                if not old_password:
                    raise ValidationError('Current password is required')
                if not user.check_password(old_password):
                    raise ValidationError('Current password is incorrect')
                if new_password != confirm_password:
                    raise ValidationError('New passwords do not match')
                user.set_password(new_password)
            
            user.save()
            messages.success(request, 'Profile updated successfully!')
            
            # Re-login if password was changed
            if new_password:
                auth_login(request, user)
                
            return redirect('user_dashboard')
            
        except ValidationError as e:
            messages.error(request, str(e))
    
    return render(request, 'users/edit_profile.html', {'user': request.user})

@login_required
def user_dashboard(request):
    if request.user.is_vendor:
        return redirect('vendor_dashboard')
    
    # Get recent orders
    recent_orders = Order.objects.filter(user=request.user).order_by('-ordered_at')[:5]
    total_orders = Order.objects.filter(user=request.user).count()
    
    # Get cart count
    cart_count = Cart.objects.filter(user=request.user).count()
    
    context = {
        'recent_orders': recent_orders,
        'total_orders': total_orders,
        'cart_count': cart_count
    }
    return render(request, 'users/dashboard.html', context)

@login_required
def user_logout(request):
    auth_logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('home')