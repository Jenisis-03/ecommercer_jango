from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from .models import User, Vendor, Product, Order, OrderItem, Category, ProductPrice, Subcategory, Cart, CartItem, ProductVariant
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.http import JsonResponse
from django.db import transaction
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth
import random

def home(request):
    categories = Category.objects.all().prefetch_related('subcategory_set')
    latest_products = Product.objects.select_related(
        'vendor', 'subcategory'
    ).prefetch_related(
        'productprice_set'
    ).order_by('-date_created')[:8]

    featured_products = Product.objects.filter(
        is_featured=True,
        product_status='published'
    ).order_by('-date_created')[:8]

    for product in latest_products:
        product.current_price = product.productprice_set.order_by('-updated_at').first()
    
    for product in featured_products:
        product.current_price = product.productprice_set.order_by('-updated_at').first()

    context = {
        'categories': categories,
        'latest_products': latest_products,
        'featured_products': featured_products,
    }
    return render(request, 'home.html', context)

@login_required
def check_stock(request, product_id):
    try:
        product = get_object_or_404(Product, id=product_id)
        current_price = product.productprice_set.order_by('-updated_at').first()
        
        if not current_price:
            return JsonResponse({
                'error': 'Product price not available'
            }, status=404)
            
        return JsonResponse({
            'stock': current_price.stock_quantity,
            'available': current_price.stock_quantity > 0,
            'product_name': product.product_name,
            'price': current_price.price
        })
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=404)

def generate_otp():
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def send_otp_email(email, otp):
    try:
        subject = 'Your OTP for Login'
        message = f'''
        Hello,

        Your OTP for login is: {otp}

        This OTP is valid for 5 minutes.

        If you didn't request this OTP, please ignore this email.

        Best regards,
        Your E-commerce Team
        '''
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [email]
        
        print(f"Sending OTP email to: {email}")  # Debug log
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False
        )
        print("OTP email sent successfully")  # Debug log
        return True
    except Exception as e:
        print(f"Error sending OTP email: {str(e)}")  # Debug log
        return False

def user_signup(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        try:
            validate_email(email)
            validate_password(password)
        except ValidationError as e:
            messages.error(request, '\n'.join(e.messages))
            return redirect('user_signup')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return redirect('user_signup')
        
        try:
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            messages.success(request, 'Account created successfully')
            return redirect('login')
        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')
            return redirect('user_signup')
            
    return render(request, 'accounts/user_signup.html')

def vendor_signup(request):
    if request.method == 'POST':
        business_name = request.POST.get('business_name')
        contact_email = request.POST.get('contact_email')
        shop_address = request.POST.get('shop_address')
        password = request.POST.get('password')
        
        try:
            validate_email(contact_email)
            validate_password(password)
        except ValidationError as e:
            messages.error(request, '\n'.join(e.messages))
            return redirect('vendor_signup')
            
        if Vendor.objects.filter(contact_email=contact_email).exists():
            messages.error(request, 'Email already exists')
            return redirect('vendor_signup')
        
        try:
            # Create a temporary user to hash the password
            temp_user = User()
            temp_user.set_password(password)
            password_hash = temp_user.password  # This is the hashed password
            
            vendor = Vendor.objects.create(
                business_name=business_name,
                contact_email=contact_email,
                shop_address=shop_address,
                password_hash=password_hash
            )
            messages.success(request, 'Vendor account created successfully')
            return redirect('login')
        except Exception as e:
            messages.error(request, f'Error creating vendor account: {str(e)}')
            return redirect('vendor_signup')
            
    return render(request, 'accounts/vendor_signup.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type')
        
        if not email or not password:
            messages.error(request, 'Please provide both email and password')
            return redirect('login')
        
        if user_type == 'admin':
            user = authenticate(request, email=email, password=password)
            if user is not None and user.is_staff:
                login(request, user)
                messages.success(request, 'Welcome to the admin dashboard!')
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'Invalid credentials or insufficient permissions.')
                return redirect('login')
        
        elif user_type == 'user':
            try:
                user = User.objects.get(email=email)
                if user.check_password(password):
                    # Generate and send OTP
                    otp = generate_otp()
                    if send_otp_email(email, otp):
                        # Store OTP in session
                        request.session['otp'] = otp
                        request.session['user_id'] = user.id
                        request.session['user_type'] = 'user'
                        messages.info(request, 'OTP has been sent to your email')
                        return redirect('verify_otp')
                    else:
                        messages.error(request, 'Failed to send OTP. Please try again.')
            except User.DoesNotExist:
                messages.error(request, 'No user found with this email')
        elif user_type == 'vendor':
            try:
                vendor = Vendor.objects.get(contact_email=email)
                # Create a temporary user to check the password
                temp_user = User()
                temp_user.password = vendor.password_hash
                if temp_user.check_password(password):
                    # Generate and send OTP
                    otp = generate_otp()
                    if send_otp_email(email, otp):
                        # Store OTP in session
                        request.session['otp'] = otp
                        request.session['vendor_id'] = vendor.id
                        request.session['user_type'] = 'vendor'
                        messages.info(request, 'OTP has been sent to your email')
                        return redirect('verify_otp')
                    else:
                        messages.error(request, 'Failed to send OTP. Please try again.')
                else:
                    messages.error(request, 'Invalid password')
            except Vendor.DoesNotExist:
                messages.error(request, 'No vendor found with this email')
        else:
            messages.error(request, 'Invalid user type selected')
        
        return redirect('login')
    
    return render(request, 'accounts/login.html')

def verify_otp(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        stored_otp = request.session.get('otp')
        user_type = request.session.get('user_type')
        
        if entered_otp == stored_otp:
            if user_type == 'user':
                user_id = request.session.get('user_id')
                user = User.objects.get(id=user_id)
                login(request, user)
                messages.success(request, 'Login successful')
                return redirect('user_dashboard')
            elif user_type == 'vendor':
                vendor_id = request.session.get('vendor_id')
                vendor = Vendor.objects.get(id=vendor_id)
                
                # Get or create a user for the vendor
                try:
                    user = User.objects.get(email=vendor.contact_email)
                except User.DoesNotExist:
                    # Create a new user only if one doesn't exist
                    user = User.objects.create_user(
                        email=vendor.contact_email,
                        password=vendor.password_hash,
                        first_name=vendor.business_name,
                        last_name=''
                    )
                
                # Link the vendor to the user
                vendor.user = user
                vendor.save()
                
                login(request, user)
                request.session['vendor_id'] = vendor_id
                messages.success(request, 'Login successful')
                return redirect('vendor_dashboard')
        else:
            messages.error(request, 'Invalid OTP')
            return redirect('verify_otp')
    
    return render(request, 'accounts/verify_otp.html')

@login_required
def user_dashboard(request):
    user = request.user
    orders = Order.objects.filter(user=user).order_by('-order_date')
    
    # Calculate total spent
    total_spent = orders.aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Get recent orders (last 5)
    recent_orders = orders[:5]
    
    # Get order statistics
    order_stats = {
        'total_orders': orders.count(),
        'total_spent': total_spent,
        'average_order_value': total_spent / orders.count() if orders.count() > 0 else 0
    }
    
    context = {
        'user': user,
        'orders': recent_orders,
        'order_stats': order_stats,
        'total_orders': orders.count()
    }
    return render(request, 'accounts/user_dashboard.html', context)

def vendor_dashboard(request):
    if 'vendor_id' not in request.session:
        return redirect('login')
    
    vendor = get_object_or_404(Vendor, id=request.session['vendor_id'])
    products = Product.objects.filter(vendor=vendor)
    
    # Calculate total sales using F expressions
    total_sales = OrderItem.objects.filter(
        product__vendor=vendor
    ).aggregate(
        total=Sum(ExpressionWrapper(
            F('price_at_time') * F('quantity'),
            output_field=DecimalField()
        ))
    )['total'] or 0
    
    # Get monthly sales data for the chart
    monthly_sales = OrderItem.objects.filter(
        product__vendor=vendor
    ).annotate(
        month=TruncMonth('order__order_date')
    ).values('month').annotate(
        revenue=Sum(ExpressionWrapper(
            F('price_at_time') * F('quantity'),
            output_field=DecimalField()
        ))
    ).order_by('month')
    
    context = {
        'vendor': vendor,
        'products': products,
        'total_sales': total_sales,
        'monthly_sales': list(monthly_sales)  # Convert to list for JSON serialization
    }
    
    return render(request, 'accounts/vendor_dashboard.html', context)

@login_required
def add_to_cart(request, product_id):
    if request.method == 'POST':
        try:
            product = get_object_or_404(Product, id=product_id)
            quantity = int(request.POST.get('quantity', 1))
            
            # Get or create cart for the user
            cart, created = Cart.objects.get_or_create(user=request.user)
            
            # Check if product is already in cart
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                defaults={'quantity': quantity}
            )
            
            if not created:
                cart_item.quantity += quantity
                cart_item.save()
            
            messages.success(request, f'{product.product_name} added to cart!')
            return redirect('view_cart')
            
        except Exception as e:
            messages.error(request, f'Error adding to cart: {str(e)}')
            return redirect('home')
    
    return redirect('home')

@login_required
def view_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.cartitem_set.select_related('product').all()
    
    # Get current prices for all products
    for item in cart_items:
        item.current_price = item.product.productprice_set.order_by('-updated_at').first()
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
    }
    return render(request, 'accounts/cart.html', context)

@login_required
def update_cart_item(request, item_id):
    if request.method == 'POST':
        try:
            cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
            quantity = int(request.POST.get('quantity', 1))
            
            if quantity > 0:
                cart_item.quantity = quantity
                cart_item.save()
                messages.success(request, 'Cart updated successfully!')
            else:
                cart_item.delete()
                messages.success(request, 'Item removed from cart!')
                
        except Exception as e:
            messages.error(request, f'Error updating cart: {str(e)}')
    
    return redirect('view_cart')

@login_required
def remove_from_cart(request, item_id):
    if request.method == 'POST':
        try:
            cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
            cart_item.delete()
            messages.success(request, 'Item removed from cart!')
        except Exception as e:
            messages.error(request, f'Error removing item: {str(e)}')
    
    return redirect('view_cart')

@login_required
@transaction.atomic
def checkout(request):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        if not cart:
            messages.error(request, 'Your cart is empty')
            return redirect('view_cart')
        
        # Create order
        order = Order.objects.create(
            user=request.user,
            total_amount=0,
            status='pending'
        )
        
        total = 0
        for product_id, item in cart.items():
            product = get_object_or_404(Product, id=product_id)
            current_price = product.productprice_set.order_by('-updated_at').first()
            
            if not current_price or current_price.stock_quantity < item['quantity']:
                order.delete()
                messages.error(request, f'Product {product.product_name} is no longer available in requested quantity')
                return redirect('view_cart')
            
            # Create order item
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item['quantity'],
                price_at_time=current_price.price
            )
            
            # Update stock
            current_price.stock_quantity -= item['quantity']
            current_price.save()
            
            total += item['quantity'] * float(current_price.price)
        
        # Update order total
        order.total_amount = total
        order.save()
        
        # Clear cart
        request.session['cart'] = {}
        
        messages.success(request, 'Order placed successfully')
        return redirect('order_confirmation', order_id=order.id)
    
    return redirect('view_cart')

@login_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'accounts/order_confirmation.html', {'order': order})

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-order_date')
    return render(request, 'accounts/order_history.html', {'orders': orders})

def logout_view(request):
    logout(request)
    if 'vendor_id' in request.session:
        del request.session['vendor_id']
    return redirect('home')

def is_vendor(user):
    return hasattr(user, 'vendor')

@login_required(login_url='login')
@user_passes_test(is_vendor, login_url='login')
def add_product(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get form data
                product_name = request.POST.get('product_name')
                product_description = request.POST.get('product_description')
                subcategory_id = request.POST.get('subcategory')
                product_status = request.POST.get('product_status', 'draft')
                is_featured = request.POST.get('is_featured') == 'on'
                
                # Get dimensions
                product_weight = request.POST.get('product_weight')
                product_length = request.POST.get('product_length')
                product_width = request.POST.get('product_width')
                product_height = request.POST.get('product_height')
                
                # Get SEO information
                meta_title = request.POST.get('meta_title')
                meta_description = request.POST.get('meta_description')
                meta_keywords = request.POST.get('meta_keywords')
                canonical_url = request.POST.get('canonical_url')
                
                # Validate required fields
                if not all([product_name, product_description, subcategory_id]):
                    messages.error(request, 'Please fill in all required fields.')
                    return redirect('add_product')
                
                # Get subcategory
                subcategory = Subcategory.objects.get(id=subcategory_id)
                
                # Create product
                product = Product.objects.create(
                    vendor=request.user.vendor,
                    product_name=product_name,
                    product_description=product_description,
                    subcategory=subcategory,
                    product_status=product_status,
                    is_featured=is_featured,
                    product_weight=product_weight if product_weight else None,
                    product_length=product_length if product_length else None,
                    product_width=product_width if product_width else None,
                    product_height=product_height if product_height else None,
                    meta_title=meta_title,
                    meta_description=meta_description,
                    meta_keywords=meta_keywords,
                    canonical_url=canonical_url
                )
                
                # Handle image upload
                if 'image' in request.FILES:
                    product.image = request.FILES['image']
                    product.save()
                
                # Handle variants
                variants = []
                i = 0
                while f'variants[{i}][color]' in request.POST:
                    color = request.POST.get(f'variants[{i}][color]')
                    size = request.POST.get(f'variants[{i}][size]')
                    price = request.POST.get(f'variants[{i}][price]')
                    stock = request.POST.get(f'variants[{i}][stock]')
                    sku = request.POST.get(f'variants[{i}][sku]')
                    
                    if all([color, size, price, stock, sku]):
                        variants.append({
                            'color': color,
                            'size': size,
                            'price': price,
                            'stock': stock,
                            'sku': sku
                        })
                    i += 1
                
                if not variants:
                    raise ValidationError('At least one variant is required')
                
                # Create variants
                for variant in variants:
                    ProductVariant.objects.create(
                        product=product,
                        color=variant['color'],
                        size=variant['size'],
                        price=variant['price'],
                        stock=variant['stock'],
                        sku=variant['sku']
                    )
                
                messages.success(request, 'Product added successfully!')
                return redirect('vendor_dashboard')
                
        except Subcategory.DoesNotExist:
            messages.error(request, 'Invalid category selected.')
            return redirect('add_product')
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('add_product')
        except Exception as e:
            messages.error(request, f'Error adding product: {str(e)}')
            return redirect('add_product')
    
    # Get all categories for the form
    categories = Category.objects.all().prefetch_related('subcategory_set')
    
    context = {
        'categories': categories,
    }
    return render(request, 'accounts/add_product.html', context)

@login_required
def edit_product(request, pk):
    if not request.user.is_vendor:
        messages.error(request, 'Access denied. Vendor account required.')
        return redirect('dashboard')
    
    try:
        product = Product.objects.get(pk=pk, vendor=request.user)
        current_price = product.productprice_set.order_by('-updated_at').first()
    except Product.DoesNotExist:
        messages.error(request, 'Product not found')
        return redirect('vendor_dashboard')
    
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description')
            price = request.POST.get('price')
            stock = request.POST.get('stock')
            subcategory_id = request.POST.get('subcategory')
            
            if not all([name, description, price, stock, subcategory_id]):
                messages.error(request, 'All fields are required')
                return render(request, 'accounts/edit_product.html', {
                    'product': product,
                    'current_price': current_price,
                    'subcategories': Subcategory.objects.all()
                })
                
            try:
                price = float(price)
                stock = int(stock)
                if price <= 0 or stock < 0:
                    raise ValueError
            except ValueError:
                messages.error(request, 'Invalid price or stock value')
                return render(request, 'accounts/edit_product.html', {
                    'product': product,
                    'current_price': current_price,
                    'subcategories': Subcategory.objects.all()
                })
            
            with transaction.atomic():
                product.product_name = name
                product.description = description
                product.subcategory_id = subcategory_id
                
                if 'image' in request.FILES:
                    product.image_url = request.FILES['image'].url
                
                product.save()
                
                if not current_price or current_price.price != price or current_price.stock_quantity != stock:
                    ProductPrice.objects.create(
                        product=product,
                        price=price,
                        stock_quantity=stock
                    )
            
            messages.success(request, 'Product updated successfully')
            return redirect('vendor_dashboard')
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')
            return render(request, 'accounts/edit_product.html', {
                'product': product,
                'current_price': current_price,
                'subcategories': Subcategory.objects.all()
            })
    
    return render(request, 'accounts/edit_product.html', {
        'product': product,
        'current_price': current_price,
        'subcategories': Subcategory.objects.all()
    })

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
def rate_product(request, product_id):
    if request.method == 'POST':
        rating = request.POST.get('rating')
        product = get_object_or_404(Product, id=product_id)
        if rating and rating.isdigit() and 1 <= int(rating) <= 5:
            product.rating = (product.rating + int(rating)) / 2 if product.rating else int(rating)
            product.save()
            messages.success(request, 'Thank you for rating this product')
    return redirect('home')

@staff_member_required
def admin_dashboard(request):
    if not request.user.is_staff:
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')
    
    # Get all users with their order information
    users = User.objects.annotate(
        total_spent=Sum('order__total_amount')
    ).prefetch_related('order_set').order_by('-date_joined')
    
    # Get all vendors with their product and sales information
    vendors = Vendor.objects.annotate(
        total_sales=Sum('product__orderitem__price_at_time')
    ).prefetch_related('product_set').order_by('-created_at')
    
    # Get all products with their category and vendor information
    products = Product.objects.select_related(
        'vendor',
        'subcategory',
        'subcategory__category'
    ).order_by('-date_created')
    
    context = {
        'users': users,
        'vendors': vendors,
        'products': products,
    }
    
    return render(request, 'accounts/admin_dashboard.html', context)

@login_required
def edit_profile(request):
    if request.method == 'POST':
        user = request.user
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        address = request.POST.get('address')
        
        # Check if email is already taken by another user
        if email != user.email and User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return redirect('user_dashboard')
        
        try:
            user.first_name = first_name
            user.last_name = last_name
            user.email = email
            user.address = address
            user.save()
            messages.success(request, 'Profile updated successfully')
        except Exception as e:
            messages.error(request, f'Error updating profile: {str(e)}')
        
        return redirect('user_dashboard')
    
    return redirect('user_dashboard')

def get_subcategories(request, category_id):
    try:
        subcategories = Subcategory.objects.filter(category_id=category_id).values('id', 'subcategory_name')
        return JsonResponse(list(subcategories), safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

def debug_categories(request):
    categories = Category.objects.all().prefetch_related('subcategory_set')
    output = []
    for category in categories:
        subcategories = [sub.subcategory_name for sub in category.subcategory_set.all()]
        output.append(f"{category.category_name}: {', '.join(subcategories)}")
    return JsonResponse({'categories': output})

def admin_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, email=email, password=password)
        
        if user is not None and user.is_staff:
            login(request, user)
            messages.success(request, 'Welcome to the admin dashboard!')
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Invalid credentials or insufficient permissions.')
    
    return render(request, 'accounts/admin_login.html')

@staff_member_required
def admin_add_user(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        try:
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            messages.success(request, 'User added successfully')
        except Exception as e:
            messages.error(request, f'Error adding user: {str(e)}')
    
    return redirect('admin_dashboard')

@staff_member_required
def admin_edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        user.email = request.POST.get('email')
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        
        if request.POST.get('password'):
            user.set_password(request.POST.get('password'))
        
        try:
            user.save()
            messages.success(request, 'User updated successfully')
        except Exception as e:
            messages.error(request, f'Error updating user: {str(e)}')
        
        return redirect('admin_dashboard')
    
    return render(request, 'accounts/admin_edit_user.html', {'user': user})

@staff_member_required
def admin_delete_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        try:
            user.delete()
            messages.success(request, 'User deleted successfully')
        except Exception as e:
            messages.error(request, f'Error deleting user: {str(e)}')
    
    return redirect('admin_dashboard')

@staff_member_required
def admin_add_vendor(request):
    if request.method == 'POST':
        business_name = request.POST.get('business_name')
        contact_email = request.POST.get('contact_email')
        shop_address = request.POST.get('shop_address')
        password = request.POST.get('password')
        
        try:
            # Create a temporary user to hash the password
            temp_user = User()
            temp_user.set_password(password)
            password_hash = temp_user.password
            
            vendor = Vendor.objects.create(
                business_name=business_name,
                contact_email=contact_email,
                shop_address=shop_address,
                password_hash=password_hash
            )
            messages.success(request, 'Vendor added successfully')
        except Exception as e:
            messages.error(request, f'Error adding vendor: {str(e)}')
    
    return redirect('admin_dashboard')

@staff_member_required
def admin_edit_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendor, id=vendor_id)
    
    if request.method == 'POST':
        vendor.business_name = request.POST.get('business_name')
        vendor.contact_email = request.POST.get('contact_email')
        vendor.shop_address = request.POST.get('shop_address')
        
        if request.POST.get('password'):
            temp_user = User()
            temp_user.set_password(request.POST.get('password'))
            vendor.password_hash = temp_user.password
        
        try:
            vendor.save()
            messages.success(request, 'Vendor updated successfully')
        except Exception as e:
            messages.error(request, f'Error updating vendor: {str(e)}')
        
        return redirect('admin_dashboard')
    
    return render(request, 'accounts/admin_edit_vendor.html', {'vendor': vendor})

@staff_member_required
def admin_delete_vendor(request, vendor_id):
    if request.method == 'POST':
        vendor = get_object_or_404(Vendor, id=vendor_id)
        try:
            vendor.delete()
            messages.success(request, 'Vendor deleted successfully')
        except Exception as e:
            messages.error(request, f'Error deleting vendor: {str(e)}')
    
    return redirect('admin_dashboard')

@staff_member_required
def admin_add_product(request):
    if request.method == 'POST':
        try:
            vendor = Vendor.objects.get(id=request.POST.get('vendor'))
            subcategory = Subcategory.objects.get(id=request.POST.get('subcategory'))
            
            product = Product.objects.create(
                vendor=vendor,
                product_name=request.POST.get('product_name'),
                subcategory=subcategory,
                base_price=request.POST.get('base_price'),
                available_stock=request.POST.get('available_stock'),
                product_status='published'
            )
            
            if 'image' in request.FILES:
                product.image = request.FILES['image']
                product.save()
            
            messages.success(request, 'Product added successfully')
        except Exception as e:
            messages.error(request, f'Error adding product: {str(e)}')
    
    return redirect('admin_dashboard')

@staff_member_required
def admin_edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        try:
            product.vendor = Vendor.objects.get(id=request.POST.get('vendor'))
            product.subcategory = Subcategory.objects.get(id=request.POST.get('subcategory'))
            product.product_name = request.POST.get('product_name')
            product.base_price = request.POST.get('base_price')
            product.available_stock = request.POST.get('available_stock')
            product.product_status = request.POST.get('product_status')
            
            if 'image' in request.FILES:
                product.image = request.FILES['image']
            
            product.save()
            messages.success(request, 'Product updated successfully')
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')
        
        return redirect('admin_dashboard')
    
    return render(request, 'accounts/admin_edit_product.html', {
        'product': product,
        'vendors': Vendor.objects.all(),
        'categories': Category.objects.all(),
        'subcategories': Subcategory.objects.filter(category=product.subcategory.category)
    })

@staff_member_required
def admin_delete_product(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        try:
            product.delete()
            messages.success(request, 'Product deleted successfully')
        except Exception as e:
            messages.error(request, f'Error deleting product: {str(e)}')
    
    return redirect('admin_dashboard')
