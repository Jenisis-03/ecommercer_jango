from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.core.mail import send_mail
from django.core.validators import validate_email  # Add this import
from django.contrib.auth.password_validation import validate_password  # Add this import
from .models import CustomUser
import random
from django.contrib.auth.decorators import login_required
from .models import Product
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.core.cache import cache

def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def signup(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        is_vendor = request.POST.get('is_vendor') == 'true'
        
        # Validate email
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Invalid email format')
            return redirect('signup')
            
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return redirect('signup')
        
        # Validate password
        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, '\n'.join(e.messages))
            return redirect('signup')
        
        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            is_vendor=is_vendor
        )
        
        if is_vendor:
            shop_name = request.POST.get('shop_name')
            shop_address = request.POST.get('shop_address')
            user.shop_name = shop_name
            user.shop_address = shop_address
            user.save()
            
        messages.success(request, 'Account created successfully')
        return redirect('login')
    return render(request, 'accounts/signup.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Rate limiting
        cache_key = f'otp_attempts_{email}'
        attempts = cache.get(cache_key, 0)
        if attempts >= 3:  # Limit to 3 attempts per 15 minutes
            messages.error(request, 'Too many OTP attempts. Please try again later.')
            return render(request, 'accounts/login.html')

        try:
            user = CustomUser.objects.get(email=email)
            if user.check_password(password):
                otp = generate_otp()
                user.otp = otp
                user.otp_created_at = timezone.now()
                user.save()
                
                # Increment attempt counter
                cache.set(cache_key, attempts + 1, 900)  # 15 minutes timeout
                
                # Send OTP via email
                # Line 85-90: In login_view function
                # Add this import at the top
                from django.conf import settings
                
                # Then replace the send_mail call with:
                send_mail(
                    'Login OTP',
                    f'Your OTP for login is: {otp}',
                    settings.EMAIL_HOST_USER,
                    [email],
                    fail_silently=False,
                )
                
                return redirect('verify_otp')
            else:
                messages.error(request, 'Invalid credentials')
        except CustomUser.DoesNotExist:
            messages.error(request, 'User does not exist')
    
    return render(request, 'accounts/login.html')

def verify_otp(request):
    if request.method == 'POST':
        otp = request.POST.get('otp')
        try:
            user = CustomUser.objects.get(otp=otp)
            # Add OTP expiration check
            if not user.otp_created_at or timezone.now() - user.otp_created_at > timedelta(minutes=10):
                messages.error(request, 'OTP has expired')
                return render(request, 'accounts/verify_otp.html')
            
            user.otp_verified = True
            user.otp = None
            user.otp_created_at = None
            user.save()
            login(request, user)
            return redirect('dashboard')
        except CustomUser.DoesNotExist:
            messages.error(request, 'Invalid OTP')
    
    return render(request, 'accounts/verify_otp.html')

def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'accounts/dashboard.html')

def signout(request):
    logout(request)
    return redirect('login')


def vendor_signup(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        shop_name = request.POST.get('shop_name')
        shop_address = request.POST.get('shop_address')
        
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return redirect('vendor_signup')
        
        # Line 142-149: In vendor_signup function
        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            is_vendor=True,
            shop_name=shop_name,
            shop_address=shop_address
        )
        messages.success(request, 'Vendor account created successfully')
        return redirect('login')
    return render(request, 'accounts/vendor_signup.html')

@login_required
def vendor_dashboard(request):
    if not request.user.is_vendor:
        messages.error(request, 'Access denied. Vendor account required.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        image = request.FILES.get('image')
        
        try:
            product = Product.objects.create(
                vendor=request.user,
                name=name,
                description=description,
                price=price,
                stock=stock,
                image=image
            )
            messages.success(request, 'Product added successfully')
        except Exception as e:
            messages.error(request, f'Error adding product: {str(e)}')
    
    # Get vendor's products
    products = Product.objects.filter(vendor=request.user).order_by('-created_at')
    return render(request, 'accounts/vendor_dashboard.html', {'products': products})

@login_required
def add_product(request):
    if not request.user.is_vendor:
        return redirect('dashboard')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        image = request.FILES.get('image')
        
        Product.objects.create(
            vendor=request.user,
            name=name,
            description=description,
            price=price,
            stock=stock,
            image=image
        )
        messages.success(request, 'Product added successfully')
        return redirect('vendor_dashboard')
    
    return render(request, 'accounts/add_product.html')

@login_required
def edit_product(request, pk):
    if not request.user.is_vendor:
        return redirect('dashboard')
    
    try:
        product = Product.objects.get(pk=pk, vendor=request.user)
    except Product.DoesNotExist:
        messages.error(request, 'Product not found')
        return redirect('vendor_dashboard')
    
    if request.method == 'POST':
        product.name = request.POST.get('name')
        product.description = request.POST.get('description')
        product.price = request.POST.get('price')
        product.stock = request.POST.get('stock')
        
        if 'image' in request.FILES:
            product.image = request.FILES['image']
        
        product.save()
        messages.success(request, 'Product updated successfully')
        return redirect('vendor_dashboard')
    
    return render(request, 'accounts/edit_product.html', {'product': product})

@login_required
def delete_product(request, pk):
    if not request.user.is_vendor:
        return redirect('dashboard')
    
    try:
        product = Product.objects.get(pk=pk, vendor=request.user)
        product.delete()
        messages.success(request, 'Product deleted successfully')
    except Product.DoesNotExist:
        messages.error(request, 'Product not found')
    
    return redirect('vendor_dashboard')
