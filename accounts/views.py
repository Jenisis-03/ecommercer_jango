from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password
from django.conf import settings 
from .models import CustomUser, Product, Order, OrderItem, Category
import random
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.db import transaction
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count
from django.db.models.functions import TruncMonth

def home(request):
    # Get all categories with their subcategories
    categories = Category.objects.all().prefetch_related('subcategory_set')
    
    # Get latest products with their current prices
    latest_products = Product.objects.select_related(
        'vendor', 'subcategory'
    ).prefetch_related(
        'productprice_set'
    ).order_by('-created_at')[:8]

    # Get all products for featured section (you might want to add a featured flag later)
    featured_products = Product.objects.select_related(
        'vendor', 'subcategory'
    ).prefetch_related(
        'productprice_set'
    ).order_by('?')[:4]  # Random selection for now

    context = {
        'categories': categories,
        'latest_products': latest_products,
        'featured_products': featured_products,
    }
    return render(request, 'home.html', context)

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
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type')
        
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            # Check if user type matches
            if user_type == 'admin' and not user.is_staff:
                messages.error(request, 'Invalid admin credentials')
                return JsonResponse({'error': 'Invalid admin credentials'})
            elif user_type == 'vendor' and not user.is_vendor:
                messages.error(request, 'Invalid vendor credentials')
                return JsonResponse({'error': 'Invalid vendor credentials'})
            elif user_type == 'user' and (user.is_vendor or user.is_staff):
                messages.error(request, 'Invalid user credentials')
                return JsonResponse({'error': 'Invalid user credentials'})

            # For admin, directly log in without OTP
            if user_type == 'admin':
                login(request, user)
                return JsonResponse({'redirect': '/admin/dashboard/'})

            # For users and vendors, generate and send OTP
            otp = generate_otp()
            cache.set(f'login_otp_{email}', otp, timeout=300)  # 5 minutes timeout
            
            # Send OTP via email
            send_mail(
                'Login OTP',
                f'Your OTP for login is: {otp}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            return JsonResponse({'require_otp': True})
        else:
            messages.error(request, 'Invalid credentials')
            return JsonResponse({'error': 'Invalid credentials'})
    
    return render(request, 'accounts/auth.html')

def signup(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type')
        
        try:
            validate_email(email)
            validate_password(password)
        except ValidationError as e:
            messages.error(request, '\n'.join(e.messages))
            return JsonResponse({'error': e.messages})
            
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return JsonResponse({'error': 'Email already exists'})
        
        # Generate and send OTP
        otp = generate_otp()
        cache.set(f'signup_otp_{email}', {
            'otp': otp,
            'data': {
                'email': email,
                'password': password,
                'user_type': user_type,
                'shop_name': request.POST.get('shop_name'),
                'shop_address': request.POST.get('shop_address')
            }
        }, timeout=300)  # 5 minutes timeout
        
        send_mail(
            'Signup OTP',
            f'Your OTP for signup is: {otp}',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        return JsonResponse({'require_otp': True})
            
    return render(request, 'accounts/auth.html')

def verify_otp(request):
    if request.method == 'POST':
        otp = request.POST.get('otp')
        email = request.POST.get('email')
        
        # Check if it's a login OTP
        stored_login_otp = cache.get(f'login_otp_{email}')
        if stored_login_otp and stored_login_otp == otp:
            user = CustomUser.objects.get(email=email)
            login(request, user)
            cache.delete(f'login_otp_{email}')
            
            if user.is_vendor:
                return JsonResponse({'redirect': '/vendor/dashboard/'})
            return JsonResponse({'redirect': '/user/dashboard/'})
        
        # Check if it's a signup OTP
        stored_signup_data = cache.get(f'signup_otp_{email}')
        if stored_signup_data and stored_signup_data['otp'] == otp:
            data = stored_signup_data['data']
            
            try:
                user = CustomUser.objects.create_user(
                    email=data['email'],
                    password=data['password'],
                    is_vendor=data['user_type'] == 'vendor'
                )
                
                if data['user_type'] == 'vendor':
                    if not data['shop_name'] or len(data['shop_name']) < 3:
                        user.delete()
                        return JsonResponse({'error': 'Shop name must be at least 3 characters long'})
                        
                    if not data['shop_address'] or len(data['shop_address']) < 10:
                        user.delete()
                        return JsonResponse({'error': 'Shop address must be at least 10 characters long'})
                        
                    user.shop_name = data['shop_name']
                    user.shop_address = data['shop_address']
                    user.save()
                
                login(request, user)
                cache.delete(f'signup_otp_{email}')
                
                if user.is_vendor:
                    return JsonResponse({'redirect': '/vendor/dashboard/'})
                return JsonResponse({'redirect': '/user/dashboard/'})
                
            except Exception as e:
                return JsonResponse({'error': str(e)})
        
        return JsonResponse({'error': 'Invalid OTP'})
    
    return JsonResponse({'error': 'Invalid request method'})

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
        
        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, 'Invalid email format')
            return redirect('vendor_signup')
            
        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return redirect('vendor_signup')
        
        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, '\n'.join(e.messages))
            return redirect('vendor_signup')
            
        if not shop_name or len(shop_name) < 3:
            messages.error(request, 'Shop name must be at least 3 characters long')
            return redirect('vendor_signup')
            
        if not shop_address or len(shop_address) < 10:
            messages.error(request, 'Shop address must be at least 10 characters long')
            return redirect('vendor_signup')
        
        try:
            user = CustomUser.objects.create_user(
                email=email,
                password=password,
                is_vendor=True,
                shop_name=shop_name,
                shop_address=shop_address
            )
            messages.success(request, 'Vendor account created successfully')
            return redirect('login')
        except Exception as e:
            messages.error(request, f'Error creating vendor account: {str(e)}')
            return redirect('vendor_signup')
            
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
        messages.error(request, 'Access denied. Vendor account required.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description')
            price = request.POST.get('price')
            stock = request.POST.get('stock')
            image = request.FILES.get('image')
            
            if not all([name, description, price, stock]):
                messages.error(request, 'All fields are required')
                return redirect('add_product')
                
            try:
                price = float(price)
                stock = int(stock)
                if price <= 0 or stock < 0:
                    raise ValueError
            except ValueError:
                messages.error(request, 'Invalid price or stock value')
                return redirect('add_product')
            
            product = Product.objects.create(
                vendor=request.user,
                name=name,
                description=description,
                price=price,
                stock=stock,
                image=image
            )
            messages.success(request, 'Product added successfully')
            return redirect('vendor_dashboard')
        except Exception as e:
            messages.error(request, f'Error adding product: {str(e)}')
            return redirect('add_product')
    
    return render(request, 'accounts/add_product.html')

@login_required
def edit_product(request, pk):
    if not request.user.is_vendor:
        messages.error(request, 'Access denied. Vendor account required.')
        return redirect('dashboard')
    
    try:
        product = Product.objects.get(pk=pk, vendor=request.user)
    except Product.DoesNotExist:
        messages.error(request, 'Product not found')
        return redirect('vendor_dashboard')
    
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description')
            price = request.POST.get('price')
            stock = request.POST.get('stock')
            
            if not all([name, description, price, stock]):
                messages.error(request, 'All fields are required')
                return render(request, 'accounts/edit_product.html', {'product': product})
                
            try:
                price = float(price)
                stock = int(stock)
                if price <= 0 or stock < 0:
                    raise ValueError
            except ValueError:
                messages.error(request, 'Invalid price or stock value')
                return render(request, 'accounts/edit_product.html', {'product': product})
            
            product.name = name
            product.description = description
            product.price = price
            product.stock = stock
            
            if 'image' in request.FILES:
                product.image = request.FILES['image']
            
            product.save()
            messages.success(request, 'Product updated successfully')
            return redirect('vendor_dashboard')
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')
            return render(request, 'accounts/edit_product.html', {'product': product})
    
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
    try:
        product = get_object_or_404(Product, id=product_id)
        
        if product.stock <= 0:
            messages.error(request, 'Sorry, this product is out of stock')
            return redirect('view_cart')
            
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_item, item_created = CartItem.objects.get_or_create(cart=cart, product=product)
        
        if not item_created:
            if cart_item.quantity >= product.stock:
                messages.error(request, 'Sorry, not enough stock available')
                return redirect('view_cart')
            cart_item.quantity += 1
            cart_item.save()
        
        messages.success(request, 'Product added to cart')
        return redirect('view_cart')
    except Exception as e:
        messages.error(request, f'Error adding to cart: {str(e)}')
        return redirect('home')

@login_required
def update_cart(request, item_id):
    try:
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'increase':
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
    except Exception as e:
        messages.error(request, f'Error updating cart: {str(e)}')
        return redirect('view_cart')

@login_required
@transaction.atomic
def checkout(request):
    try:
        cart = Cart.objects.get(user=request.user)
        if not cart.items.exists():
            messages.error(request, 'Your cart is empty')
            return redirect('view_cart')
            
        if request.method == 'POST':
            # Check if all items have sufficient stock
            for item in cart.items.all():
                if item.quantity > item.product.stock:
                    messages.error(request, f'Sorry, {item.product.name} does not have sufficient stock')
                    return redirect('view_cart')
            
            # Create order
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
            messages.success(request, 'Order placed successfully!')
            return redirect('order_confirmation', order_id=order.id)
        
        return render(request, 'accounts/checkout.html', {'cart': cart})
    except Cart.DoesNotExist:
        messages.error(request, 'Your cart is empty')
        return redirect('view_cart')
    except Exception as e:
        messages.error(request, f'Error during checkout: {str(e)}')
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

def user_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.is_vendor:
        return redirect('vendor_dashboard')
    if request.user.is_staff:
        return redirect('admin_dashboard')
    return render(request, 'accounts/dashboard.html')

@staff_member_required
def admin_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')
    
    # Get statistics for admin dashboard
    total_users = CustomUser.objects.count()
    total_vendors = CustomUser.objects.filter(is_vendor=True).count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    
    # Get recent orders
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:5]
    
    # Get monthly sales data
    monthly_sales = Order.objects.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total_sales=Sum('total_amount'),
        order_count=Count('id')
    ).order_by('month')
    
    context = {
        'total_users': total_users,
        'total_vendors': total_vendors,
        'total_products': total_products,
        'total_orders': total_orders,
        'recent_orders': recent_orders,
        'monthly_sales': monthly_sales,
    }
    
    return render(request, 'accounts/admin_dashboard.html', context)
