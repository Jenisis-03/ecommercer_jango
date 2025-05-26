from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password
from django.conf import settings 
from .models import CustomUser
import random
from django.contrib.auth.decorators import login_required
from .models import Product
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from .models import Cart, CartItem ,Order, OrderItem
from django.http import JsonResponse
def home(request):
    products = Product.objects.all().order_by('-created_at')
    if request.user.is_authenticated:
   
        context = {
            'products': products,
            'user': request.user,
        }
    else:
        
        context = {
            'products': products,
        }
    return render(request, 'accounts/home.html', context)

def home(request):
   
    products = Product.objects.all().order_by('-created_at')
    return render(request, 'accounts/home.html', {'products': products})

@login_required
def check_stock(request, product_id):
    """Check if a product has sufficient stock"""
    try:
        product = get_object_or_404(Product, id=product_id)
        return JsonResponse({
            'stock': product.stock,
            'available': product.stock > 0,
            'product_name': product.name
        })
    except Exception as e:
        return JsonResponse({
            'error': 'Product not found'
        }, status=404)
def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def signup(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        is_vendor = request.POST.get('is_vendor') == 'true'
        
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Invalid email format')
            return redirect('signup')
            
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return redirect('signup')
        
        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, '\n'.join(e.messages))
            return redirect('signup')
        
        try:
            user = CustomUser.objects.create_user(
                email=email,
                password=password,
                is_vendor=is_vendor
            )
            
            if is_vendor:
                shop_name = request.POST.get('shop_name')
                shop_address = request.POST.get('shop_address')
                
                if not shop_name or len(shop_name) < 3:
                    messages.error(request, 'Shop name must be at least 3 characters long')
                    user.delete()
                    return redirect('signup')
                    
                if not shop_address or len(shop_address) < 10:
                    messages.error(request, 'Shop address must be at least 10 characters long')
                    user.delete()
                    return redirect('signup')
                    
                user.shop_name = shop_name
                user.shop_address = shop_address
                user.save()
                
            messages.success(request, 'Account created successfully')
            return redirect('login')
        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')
            return redirect('signup')
            
    return render(request, 'accounts/signup.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()  
        password = request.POST.get('password', '')
        
        if not email or not password:
            messages.error(request, 'Both email and password are required')
            return render(request, 'accounts/login.html')
        
        # Rate limiting
        cache_key = f'otp_attempts_{email}'
        attempts = cache.get(cache_key, 0)
        if attempts >= 3:
            messages.error(request, 'Too many OTP attempts. Please try again later.')
            return render(request, 'accounts/login.html')

        try:
            user = CustomUser.objects.get(email=email)
            if user.check_password(password):
                try:
                    otp = generate_otp()
                    user.otp = otp
                    user.otp_created_at = timezone.now()
                    user.save()
                    
        
                    cache.set(cache_key, attempts + 1, 900)  # 15 minutes timeout
                    
                    # Send OTP via email
                    send_mail(
                        'Login OTP',
                        f'Your OTP for login is: {otp}',
                        settings.EMAIL_HOST_USER,
                        [email],
                        fail_silently=False,
                    )
                    
                    return redirect('verify_otp')
                except Exception as e:
                    messages.error(request, 'Error sending OTP. Please try again.')
                    return render(request, 'accounts/login.html')
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


@login_required
def search_products(request):
    query = request.GET.get('q', '')
    products = Product.objects.all()
    
    if query:
        products = products.filter(name__icontains=query)
    
    return render(request, 'accounts/home.html', {'products': products, 'query': query})

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    # Check if there's enough stock
    if product.stock <= 0:
        messages.error(request, 'Sorry, this product is out of stock')
        return redirect('view_cart')
        
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_item, item_created = CartItem.objects.get_or_create(cart=cart, product=product)
    
    if not item_created:
        # Check if there's enough stock for increment
        if cart_item.quantity >= product.stock:
            messages.error(request, 'Sorry, not enough stock available')
            return redirect('view_cart')
        cart_item.quantity += 1
        cart_item.save()
    
    messages.success(request, 'Product added to cart')
    return redirect('view_cart')

@login_required
def update_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'increase':
            # Check if there's enough stock for increment
            if cart_item.quantity >= cart_item.product.stock:
                messages.error(request, 'Sorry, not enough stock available')
                return redirect('view_cart')
            cart_item.quantity += 1
        elif action == 'decrease':
            cart_item.quantity = max(0, cart_item.quantity - 1)
        
        if cart_item.quantity == 0:
            cart_item.delete()
        else:
            cart_item.save()
    
    return redirect('view_cart')

@login_required
def checkout(request):
    try:
        cart = Cart.objects.get(user=request.user)
        if request.method == 'POST':
            # Check if all items have sufficient stock
            for item in cart.items.all():
                if item.quantity > item.product.stock:
                    messages.error(request, f'Sorry, {item.product.name} does not have sufficient stock')
                    return redirect('view_cart')
            
            order = Order.objects.create(
                user=request.user,
                full_name=request.POST.get('full_name'),
                email=request.POST.get('email'),
                address=request.POST.get('address'),
                phone=request.POST.get('phone'),
                total_amount=cart.get_total_price()
            )
            
            # Create order items and update stock
            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
                # Decrease product stock
                item.product.stock -= item.quantity
                item.product.save()
            
            cart.delete()
            return redirect('order_confirmation', order_id=order.id)
        
        return render(request, 'accounts/checkout.html', {'cart': cart})
    except Cart.DoesNotExist:
        return redirect('view_cart')

@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'accounts/order_confirmation.html', {'order': order})


@login_required
def view_cart(request):
    try:
        cart = Cart.objects.get(user=request.user)
        return render(request, 'accounts/cart.html', {'cart': cart})
    except Cart.DoesNotExist:
        return render(request, 'accounts/cart.html', {'cart': None})


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'accounts/order_history.html', {'orders': orders})


@login_required
def rate_product(request, product_id):
    if request.method == 'POST':
        rating = request.POST.get('rating')
        product = get_object_or_404(Product, id=product_id)
        if rating and rating.isdigit() and 1 <= int(rating) <= 5:
            product.rating = (product.rating + int(rating)) / 2 if product.rating else int(rating)
            product.save()
            messages.success(request, 'Thank you for rating this product')
    return redirect('home')
