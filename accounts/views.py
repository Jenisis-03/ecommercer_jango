from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.core.mail import send_mail
from .models import CustomUser
import random
from django.contrib.auth.decorators import login_required
from .models import Product

def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def signup(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        is_vendor = request.POST.get('is_vendor') == 'true'
        
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return redirect('signup')
        
        user = CustomUser.objects.create_user(
            username=name,
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
        
        try:
            user = CustomUser.objects.get(email=email)
            if user.check_password(password):
                otp = generate_otp()
                user.otp = otp
                user.save()
                
                # Send OTP via email
                send_mail(
                    'Login OTP',
                    f'Your OTP for login is: {otp}',
                    'your_email@gmail.com',
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
            user.otp_verified = True
            user.otp = None
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
        
        user = CustomUser.objects.create_user(
            username=name,
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
