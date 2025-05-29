from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib import messages
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from .models import User, Vendor, Product, Order, OrderItem, Category, ProductPrice, Subcategory, Cart, CartItem, ProductVariant, Wishlist, Address, PaymentMethod, Profile
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
from django.db.models import Q
import json
from django.core.serializers import serialize
from django.core.paginator import Paginator
import logging
from django.views.decorators.http import require_POST
import stripe
from decimal import Decimal

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

@require_POST
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return JsonResponse({'error': 'Invalid signature'}, status=400)

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        order_id = payment_intent['metadata']['order_id']
        try:
            order = Order.objects.get(id=order_id)
            order.status = 'paid'
            order.save()
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found'}, status=404)
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        order_id = payment_intent['metadata']['order_id']
        try:
            order = Order.objects.get(id=order_id)
            order.status = 'failed'
            order.save()
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Order not found'}, status=404)

    return JsonResponse({'status': 'success'})

@login_required
@require_POST
def create_payment_intent(request):
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        
        # Get the order
        order = Order.objects.get(id=order_id, user=request.user)
        
        # Create a PaymentIntent with the order amount and currency
        intent = stripe.PaymentIntent.create(
            amount=int(order.total_amount * 100),  # Convert to cents
            currency='usd',
            metadata={
                'order_id': order.id,
                'user_id': request.user.id
            }
        )
        
        return JsonResponse({
            'clientSecret': intent.client_secret
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=403)

def get_subcategories(request, category_id):
    subcategories = Subcategory.objects.filter(category_id=category_id)
    data = [{'id': sub.id, 'subcategory_name': sub.subcategory_name} for sub in subcategories]
    return JsonResponse(data, safe=False)

def home(request):
    # Get filter parameters
    category_id = request.GET.get('category')
    subcategory_id = request.GET.get('subcategory')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort = request.GET.get('sort', 'newest')
    page = request.GET.get('page', 1)

    # Base queryset - show all published products
    products = Product.objects.filter(
        product_status='published'
    ).select_related(
        'vendor',
        'subcategory',
        'subcategory__category'
    ).prefetch_related(
        'productprice_set',
        'variants'
    )

    # Apply filters
    if category_id:
        products = products.filter(subcategory__category_id=category_id)
    if subcategory_id:
        products = products.filter(subcategory_id=subcategory_id)
    if min_price:
        products = products.filter(base_price__gte=min_price)
    if max_price:
        products = products.filter(base_price__lte=max_price)

    # Apply sorting
    if sort == 'price_asc':
        products = products.order_by('base_price')
    elif sort == 'price_desc':
        products = products.order_by('-base_price')
    elif sort == 'popular':
        products = products.annotate(
            order_count=Count('orderitem')
        ).order_by('-order_count')
    else:  # newest
        products = products.order_by('-created_at')

    # Get featured products
    featured_products = Product.objects.filter(
        product_status='published',
        is_featured=True
    ).select_related(
        'vendor',
        'subcategory',
        'subcategory__category'
    ).prefetch_related(
        'productprice_set',
        'variants'
    )[:6]  # Limit to 6 featured products

    # Get categories with product counts
    categories = Category.objects.annotate(
        product_count=Count('subcategory__product', filter=Q(subcategory__product__product_status='published'))
    ).filter(product_count__gt=0)

    # Get subcategories for the selected category
    subcategories = Subcategory.objects.filter(category_id=category_id) if category_id else Subcategory.objects.none()

    # Add current prices and variant information to products
    for product in products:
        first_variant = product.variants.first()
        if first_variant:
            product.current_price = first_variant.price
            product.stock_quantity = first_variant.stock
        else:
            product.current_price = product.base_price
            product.stock_quantity = 0

    # Pagination
    paginator = Paginator(products, 12)  # Show 12 products per page
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    context = {
        'page_obj': page_obj,
        'featured_products': featured_products,
        'categories': categories,
        'subcategories': subcategories,
        'selected_category': category_id,
        'selected_subcategory': subcategory_id,
        'min_price': min_price,
        'max_price': max_price,
        'sort': sort,
    }
    return render(request, 'home.html', context)

@login_required
def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related('vendor', 'subcategory__category')
        .prefetch_related('variants'),
        id=product_id
    )
    
    # Get all variants
    variants = product.variants.all()
    
    # Get related products from the same category
    related_products = Product.objects.filter(
        subcategory=product.subcategory
    ).exclude(id=product.id)[:4]  # Get 4 related products
    
    context = {
        'product': product,
        'variants': variants,
        'related_products': related_products,
    }
    
    return render(request, 'accounts/product_detail.html', context)

def category_products(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    
    # Get filter parameters
    subcategory_id = request.GET.get('subcategory')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort = request.GET.get('sort', 'newest')
    page = request.GET.get('page', 1)

    # Base queryset
    products = Product.objects.filter(
        product_status='published',
        subcategory__category=category
    ).select_related(
        'vendor',
        'subcategory',
        'subcategory__category'
    ).prefetch_related(
        'productprice_set',
        'variants',
        'images'
    )

    # Apply filters
    if subcategory_id:
        products = products.filter(subcategory_id=subcategory_id)
    if min_price:
        products = products.filter(base_price__gte=min_price)
    if max_price:
        products = products.filter(base_price__lte=max_price)

    # Apply sorting
    if sort == 'price_asc':
        products = products.order_by('base_price')
    elif sort == 'price_desc':
        products = products.order_by('-base_price')
    elif sort == 'popular':
        products = products.annotate(
            order_count=Count('orderitem')
        ).order_by('-order_count')
    else:  # newest
        products = products.order_by('-created_at')

    # Get subcategories for this category
    subcategories = Subcategory.objects.filter(category=category)

    # Add current prices and variant information to products
    for product in products:
        first_variant = product.variants.first()
        if first_variant:
            product.current_price = first_variant.price
            product.stock_quantity = first_variant.stock
        else:
            product.current_price = product.base_price
            product.stock_quantity = 0

    # Pagination
    paginator = Paginator(products, 12)  # Show 12 products per page
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    context = {
        'category': category,
        'page_obj': page_obj,
        'subcategories': subcategories,
        'selected_subcategory': subcategory_id,
        'min_price': min_price,
        'max_price': max_price,
        'sort': sort,
    }
    return render(request, 'category_products.html', context)

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

def is_vendor(user):
    return hasattr(user, 'vendor')

def user_signup(request):
    """
    Handle user registration with proper validation and error handling.
    """
    if request.method == 'POST':
        try:
            email = request.POST.get('email')
            password = request.POST.get('password')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            
            # Validate input
            if not all([email, password, first_name, last_name]):
                messages.error(request, 'All fields are required')
                return redirect('user_signup')
            
            try:
                validate_email(email)
                validate_password(password)
            except ValidationError as e:
                messages.error(request, '\n'.join(e.messages))
                return redirect('user_signup')
                
            # Check for existing user
            if User.objects.filter(email=email).exists():
                messages.error(request, 'Email already exists')
                return redirect('user_signup')
            
            # Create user with transaction
            with transaction.atomic():
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                
                # Create associated profile
                Profile.objects.create(user=user)
                
                # Send welcome email
                try:
                    send_mail(
                        'Welcome to Our Store',
                        f'Hello {first_name},\n\nWelcome to our store! We\'re excited to have you on board.',
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=True
                    )
                except Exception as e:
                    logger.error(f"Failed to send welcome email to {email}: {str(e)}")
                
                messages.success(request, 'Account created successfully')
                return redirect('login')
                
        except Exception as e:
            logger.error(f"Error in user signup: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred during registration. Please try again.')
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
            messages.error(request, f'Validation Error: {'\n'.join(e.messages)}')
            return redirect('vendor_signup')
            
        # Check if a user with this email already exists
        if User.objects.filter(email=contact_email).exists():
            messages.error(request, 'A user with this email already exists.')
            return redirect('vendor_signup')
        
        try:
            with transaction.atomic():
                # Create a User first
                user = User.objects.create_user(
                    email=contact_email,
                    password=password,
                    first_name=business_name,  # Using business name as first name
                    last_name='',
                    is_active=True  # Ensure user is active
                )
                
                # Then create the Vendor and link to the User
                vendor = Vendor.objects.create(
                    user=user,
                    business_name=business_name,
                    shop_address=shop_address,
                )
                
                print(f"Vendor created successfully: {vendor.id}")  # Debug log
                messages.success(request, 'Vendor account created successfully. Please login.')
                return redirect('login')
        except Exception as e:
            print(f"Error creating vendor: {str(e)}")  # Debug log
            messages.error(request, f'Error creating vendor account: {str(e)}')
            return redirect('vendor_signup')
            
    return render(request, 'accounts/vendor_signup.html')

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type', 'user')
        
        # Rate limiting
        cache_key = f'login_attempts_{request.META.get("REMOTE_ADDR")}'
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:  # Maximum 5 attempts
            messages.error(request, 'Too many login attempts. Please try again later.')
            return redirect('login')
            
        try:
            user = authenticate(request, email=email, password=password)
            
            if user is not None:
                if user.is_active:
                    # Check user type
                    if user_type == 'admin' and not user.is_staff:
                        messages.error(request, 'Invalid admin credentials.')
                        return redirect('login')
                    elif user_type == 'vendor' and not hasattr(user, 'vendor'):
                        messages.error(request, 'Invalid vendor credentials.')
                        return redirect('login')
                    elif user_type == 'user' and (user.is_staff or hasattr(user, 'vendor')):
                        messages.error(request, 'Please use the correct login form for your account type.')
                        return redirect('login')
                    
                    # Generate and send OTP
                    otp = generate_otp()
                    if send_otp_email(email, otp):
                        # Store OTP and user info in session
                        request.session['otp'] = otp
                        request.session['user_id'] = user.id
                        request.session['user_type'] = user_type
                        request.session['otp_sent_time'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Reset login attempts
                        cache.delete(cache_key)
                        
                        messages.success(request, 'OTP has been sent to your email.')
                        return redirect('verify_otp')
                    else:
                        messages.error(request, 'Failed to send OTP. Please try again.')
                        return redirect('login')
                else:
                    messages.error(request, 'Your account is inactive.')
            else:
                # Increment failed attempts
                cache.set(cache_key, attempts + 1, 300)  # Store for 5 minutes
                messages.error(request, 'Invalid email or password.')
                
        except Exception as e:
            logger.error(f"Login error for {email}: {str(e)}", exc_info=True)
            messages.error(request, 'An error occurred during login. Please try again.')
            
        return redirect('login')
        
    return render(request, 'accounts/login.html')

def verify_otp(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        stored_otp = request.session.get('otp')
        user_id = request.session.get('user_id')
        user_type = request.session.get('user_type')
        otp_sent_time_str = request.session.get('otp_sent_time')

        # Check for missing session data
        if not all([stored_otp, user_id, user_type, otp_sent_time_str]):
            messages.error(request, 'Session expired. Please try logging in again.')
            return redirect('login')
            
        # Check if OTP has expired (5 minutes)
        otp_sent_time = timezone.datetime.strptime(otp_sent_time_str, '%Y-%m-%d %H:%M:%S')
        otp_sent_time = timezone.make_aware(otp_sent_time)
        time_difference = timezone.now() - otp_sent_time
        if time_difference.total_seconds() > 300:  # 5 minutes
            messages.error(request, 'OTP has expired. Please try logging in again.')
            # Clear OTP related session data
            for key in ['otp', 'user_id', 'user_type', 'otp_sent_time', 'vendor_id', 'vendor_name']:
                request.session.pop(key, None)
            return redirect('login')
            
        if entered_otp == stored_otp:
            try:
                user = User.objects.get(id=user_id)
                user.backend = 'accounts.backends.EmailBackend'
                login(request, user)
                messages.success(request, 'Login successful')

                # Clear OTP related session data
                for key in ['otp', 'user_id', 'otp_sent_time']:
                    request.session.pop(key, None)

                # Redirect based on user type
                if user_type == 'admin':
                    # Ensure user is staff for admin dashboard access
                    if user.is_staff:
                        request.session['user_type'] = 'admin' # Ensure user_type is maintained in session
                        return redirect('admin_dashboard')
                    else:
                        messages.error(request, 'Invalid credentials or insufficient permissions.')
                        logout(request)
                        return redirect('login')
                elif user_type == 'user':
                     request.session['user_type'] = 'user' # Ensure user_type is maintained in session
                     return redirect('user_dashboard')
                elif user_type == 'vendor':
                    try:
                        vendor = Vendor.objects.get(user=user)
                        if vendor.store_status == 'suspended':
                            messages.error(request, 'Your vendor account has been suspended. Please contact support.')
                            logout(request)
                            return redirect('login')
                        # Ensure vendor session data is maintained and redirect
                        request.session['user_type'] = 'vendor' # Ensure user_type is maintained in session
                        request.session['vendor_id'] = vendor.id
                        request.session['vendor_name'] = vendor.business_name
                        return redirect('vendor_dashboard')
                    except Vendor.DoesNotExist:
                        messages.error(request, 'No vendor account found for this user.')
                        logout(request)
                        return redirect('login')
                    except Exception as e:
                        print(f"Vendor verification error: {str(e)}")  # Debug log
                        messages.error(request, 'An error occurred during vendor verification.')
                        logout(request)
                        return redirect('login')
                else:
                    # Should not happen if user_type is set correctly in login_view
                    messages.error(request, 'Invalid user type in session.')
                    logout(request)
                    return redirect('login')

            except User.DoesNotExist:
                messages.error(request, 'User account not found.')
                logout(request)
                return redirect('login')
            except Exception as e:
                print(f"OTP verification error: {str(e)}")  # Debug log
                messages.error(request, 'An error occurred during verification.')
                logout(request)
                return redirect('login')
        else:
            messages.error(request, 'Invalid OTP. Please try again.')
            # Do not clear user_id or user_type here, allow them to try OTP again
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
    
    # Get user's wishlist
    wishlist = Wishlist.objects.filter(user=user).select_related('product')
    
    # Get user's addresses
    addresses = Address.objects.filter(user=user)
    
    context = {
        'user': user,
        'orders': recent_orders,
        'order_stats': order_stats,
        'wishlist': wishlist,
        'addresses': addresses,
    }
    return render(request, 'accounts/user_dashboard.html', context)

@login_required
@user_passes_test(is_vendor, login_url='login')
def vendor_dashboard(request):
    print(f"DEBUG: Accessing vendor_dashboard view for user: {request.user.email}")
    if not request.user.is_authenticated:
        messages.error(request, 'Please login to access the vendor dashboard.')
        print("DEBUG: User not authenticated, redirecting to login")
        return redirect('login')
        
    # Get vendor from session or database
    vendor = None
    if 'vendor_id' in request.session:
        print(f"DEBUG: vendor_id found in session: {request.session['vendor_id']}")
        try:
            vendor = Vendor.objects.get(id=request.session['vendor_id'], user=request.user)
            print(f"DEBUG: Vendor found using session ID: {vendor.id}")
        except Vendor.DoesNotExist:
            print("DEBUG: Vendor not found for session ID and user, clearing session data")
            # Clear invalid session data
            request.session.pop('vendor_id', None)
            request.session.pop('vendor_name', None)
    
    # If vendor not in session, try to get from database
    if not vendor:
        print("DEBUG: Vendor not found in session, attempting to fetch from database")
        try:
            vendor = Vendor.objects.get(user=request.user)
            print(f"DEBUG: Vendor found using user object: {vendor.id}")
            # Update session with vendor data
            request.session['vendor_id'] = vendor.id
            request.session['vendor_name'] = vendor.business_name
            print("DEBUG: Session updated with vendor data from database")
        except Vendor.DoesNotExist:
            messages.error(request, 'No vendor account found. Please sign up as a vendor first.')
            print("DEBUG: No vendor account found for user, redirecting to login")
            return redirect('login')
    
    # Check if vendor is suspended
    if vendor.store_status == 'suspended':
        messages.error(request, 'Your vendor account has been suspended. Please contact support.')
        print("DEBUG: Vendor account suspended, redirecting to login")
        return redirect('login')
        
    print(f"DEBUG: Vendor verification successful, proceeding to render dashboard for vendor {vendor.id}")
        
    # Fetch vendor's products efficiently
    products = Product.objects.filter(vendor=vendor).select_related(
        'subcategory'
    ).prefetch_related(
        'variants'
    ) # Using variants for price/stock as implemented previously

    # Add current prices and variant information to products for display
    for product in products:
        first_variant = product.variants.first()
        if first_variant:
            product.current_price = first_variant.price
            product.stock_quantity = first_variant.stock
        else:
            product.current_price = product.base_price # Fallback if no variants
            product.stock_quantity = 0

    context = {
        'vendor': vendor,
        'products': products,
    }
    
    return render(request, 'accounts/vendor_dashboard.html', context)

@login_required
@require_POST
def add_to_cart(request, product_id):
    try:
        product = get_object_or_404(Product, id=product_id)
        quantity = int(request.POST.get('quantity', 1))
        selected_variant_id = request.POST.get('selected_variant_id')

        # Get or create cart for the user
        cart, created = Cart.objects.get_or_create(user=request.user)

        if selected_variant_id:
            # If a variant is selected, get the variant and use its price and stock
            variant = get_object_or_404(ProductVariant, id=selected_variant_id, product=product)
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                variant=variant,
                defaults={'quantity': quantity, 'price_at_time': variant.price}
            )
            if not created:
                cart_item.quantity += quantity
                cart_item.save()
            messages.success(request, f'{product.product_name} ({variant.color}/{variant.size}) added to cart!')
        else:
            # If no variant is selected, use base price
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                variant=None,
                defaults={'quantity': quantity, 'price_at_time': product.base_price}
            )
            if not created:
                cart_item.quantity += quantity
                cart_item.save()
            messages.success(request, f'{product.product_name} added to cart!')

        # Update cart count in session
        request.session['cart_count'] = cart.cartitem_set.count()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Product added to cart successfully',
            'cart_count': request.session['cart_count']
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def view_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.cartitem_set.select_related('product', 'variant').all()
    
    # Calculate totals
    subtotal = sum(item.price_at_time * item.quantity for item in cart_items)
    shipping_cost = 50  # You can make this dynamic based on your shipping rules
    total = subtotal + shipping_cost
    
    # Update cart count in session
    request.session['cart_count'] = cart_items.count()
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'total': total,
        'cart_count': request.session['cart_count']
    }
    return render(request, 'accounts/cart.html', context)

@login_required
@require_POST
def update_cart_item(request, item_id):
    try:
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        data = json.loads(request.body)
        quantity = int(data.get('quantity', 1))
        
        if quantity > 0:
            # Check stock availability
            if cart_item.variant:
                if quantity > cart_item.variant.stock:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Only {cart_item.variant.stock} items available in stock'
                    }, status=400)
            else:
                if quantity > cart_item.product.stock:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Only {cart_item.product.stock} items available in stock'
                    }, status=400)
            
            cart_item.quantity = quantity
            cart_item.save()
            
            # Update cart count in session
            cart = Cart.objects.get(user=request.user)
            request.session['cart_count'] = cart.cartitem_set.count()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Cart updated successfully',
                'cart_count': request.session['cart_count'],
                'item_total': float(cart_item.total_price)
            })
        else:
            cart_item.delete()
            
            # Update cart count in session
            cart = Cart.objects.get(user=request.user)
            request.session['cart_count'] = cart.cartitem_set.count()
            
            return JsonResponse({
                'status': 'success',
                'message': 'Item removed from cart',
                'cart_count': request.session['cart_count']
            })
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except ValueError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid quantity value'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
@require_POST
def remove_from_cart(request, item_id):
    try:
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        cart_item.delete()
        
        # Update cart count in session
        cart = Cart.objects.get(user=request.user)
        request.session['cart_count'] = cart.cartitem_set.count()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Item removed from cart',
            'cart_count': request.session['cart_count']
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    cart_items = cart.cartitem_set.select_related('product', 'variant').all()
    
    if not cart_items.exists():
        messages.error(request, 'Your cart is empty')
        return redirect('view_cart')
    
    # Calculate totals
    subtotal = sum(item.price_at_time * item.quantity for item in cart_items)
    shipping_cost = 50  # You can make this dynamic based on your shipping rules
    tax_rate = Decimal('0.18')  # 18% GST
    tax_amount = subtotal * tax_rate
    total = subtotal + shipping_cost + tax_amount
    
    # Get user's saved addresses
    addresses = Address.objects.filter(user=request.user)
    
    # Get user's saved payment methods
    payment_methods = PaymentMethod.objects.filter(user=request.user)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get address and payment method
                address_id = request.POST.get('address_id')
                payment_method_id = request.POST.get('payment_method_id')
                
                if not address_id or not payment_method_id:
                    messages.error(request, 'Please select both shipping address and payment method')
                    return redirect('checkout')
                
                address = Address.objects.get(id=address_id, user=request.user)
                payment_method = PaymentMethod.objects.get(id=payment_method_id, user=request.user)
                
                # Create order
                order = Order.objects.create(
                    user=request.user,
                    total_amount=total,
                    shipping_address=address.street_address,
                    shipping_city=address.city,
                    shipping_state=address.state,
                    shipping_zip_code=address.zip_code,
                    shipping_country=address.country,
                    status='pending'
                )
                
                # Create order items and update stock
                for cart_item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        variant=cart_item.variant,
                        quantity=cart_item.quantity,
                        price_at_time=cart_item.price_at_time
                    )
                    
                    # Update product stock
                    if cart_item.variant:
                        cart_item.variant.stock -= cart_item.quantity
                        cart_item.variant.save()
                    else:
                        cart_item.product.stock -= cart_item.quantity
                        cart_item.product.save()
                
                # Create Stripe payment intent
                intent = stripe.PaymentIntent.create(
                    amount=int(total * 100),  # Convert to cents
                    currency='usd',
                    metadata={
                        'order_id': order.id,
                        'user_id': request.user.id
                    }
                )
                
                # Clear cart
                cart.cartitem_set.all().delete()
                request.session.pop('cart_count', None)
                
                return JsonResponse({
                    'status': 'success',
                    'order_id': order.id,
                    'client_secret': intent.client_secret,
                    'redirect_url': f'/order-confirmation/{order.id}/'
                })
                
        except Address.DoesNotExist:
            messages.error(request, 'Invalid shipping address')
        except PaymentMethod.DoesNotExist:
            messages.error(request, 'Invalid payment method')
        except Exception as e:
            messages.error(request, f'Error processing order: {str(e)}')
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'total': total,
        'addresses': addresses,
        'payment_methods': payment_methods,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    }
    return render(request, 'accounts/checkout.html', context)

@login_required
def payment(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
    except Order.DoesNotExist:
        return redirect('cart')
    
    context = {
        'order': order,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    }
    return render(request, 'accounts/payment.html', context)

@login_required
def order_confirmation(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        order_items = OrderItem.objects.filter(order=order).select_related('product')
        
        context = {
            'order': order,
            'order_items': order_items,
            'total_amount': order.total_amount,
            'order_date': order.order_date,
            'status': order.status
        }
        return render(request, 'accounts/order_confirmation.html', context)
    except Order.DoesNotExist:
        messages.error(request, 'Order not found')
        return redirect('user_dashboard')

@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user).order_by('-order_date')
    paginator = Paginator(orders, 10)  # Show 10 orders per page
    
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'orders': page_obj,
        'total_orders': orders.count(),
        'total_spent': orders.aggregate(total=Sum('total_amount'))['total'] or 0
    }
    return render(request, 'accounts/order_list.html', context)

def logout_view(request):
    logout(request)
    if 'vendor_id' in request.session:
        del request.session['vendor_id']
    return redirect('home')

@login_required(login_url='login')
@user_passes_test(is_vendor, login_url='login')
def add_product(request):
    if not request.user.is_authenticated:
        return redirect('login')
        
    # Get vendor from session
    if 'vendor_id' not in request.session:
        try:
            vendor = Vendor.objects.get(user=request.user)
            request.session['vendor_id'] = vendor.id
        except Vendor.DoesNotExist:
            messages.error(request, 'No vendor account found.')
            return redirect('login')
    
    vendor = get_object_or_404(Vendor, id=request.session['vendor_id'])
    if vendor.user != request.user:
        messages.error(request, 'Access denied.')
        return redirect('login')

    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get form data
                product_name = request.POST.get('product_name')
                product_description = request.POST.get('product_description')
                subcategory_id = request.POST.get('subcategory')
                # Set default status to published
                product_status = 'published'
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
                
                # Handle variants first to get base price
                variants = []
                base_price = None
                i = 0
                while f'variants[{i}][color]' in request.POST:
                    color = request.POST.get(f'variants[{i}][color]')
                    size = request.POST.get(f'variants[{i}][size]')
                    price = request.POST.get(f'variants[{i}][price]')
                    stock = request.POST.get(f'variants[{i}][stock]')
                    sku = request.POST.get(f'variants[{i}][sku]')
                    
                    if all([color, size, price, stock, sku]):
                        try:
                            price = float(price)
                            stock = int(stock)
                            if price <= 0 or stock < 0:
                                raise ValueError
                            variants.append({
                                'color': color,
                                'size': size,
                                'price': price,
                                'stock': stock,
                                'sku': sku
                            })
                            # Set base price from first variant
                            if base_price is None:
                                base_price = price
                        except ValueError:
                            messages.error(request, f'Invalid price or stock value for variant {i+1}')
                            return redirect('add_product')
                    i += 1
                
                if not variants:
                    messages.error(request, 'At least one variant is required')
                    return redirect('add_product')
                
                if base_price is None:
                    messages.error(request, 'Invalid base price')
                    return redirect('add_product')
                
                # Create product with base price and published status
                product = Product.objects.create(
                    vendor=vendor,
                    product_name=product_name,
                    product_description=product_description,
                    subcategory=subcategory,
                    product_status=product_status,  # Always set to published
                    is_featured=is_featured,
                    base_price=base_price,
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
                
                messages.success(request, 'Product added successfully and is now visible to all users!')
                return redirect('vendor_dashboard')
                
        except Subcategory.DoesNotExist:
            messages.error(request, 'Invalid category selected.')
            return redirect('add_product')
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('add_product')
        except Exception as e:
            print(f"Error adding product: {str(e)}")  # Debug log
            messages.error(request, f'Error adding product: {str(e)}')
            return redirect('add_product')
    
    # Get all categories for the form
    categories = Category.objects.all().prefetch_related('subcategory_set')
    
    context = {
        'categories': categories,
        'vendor': vendor,
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
    sort = request.GET.get('sort', 'newest')
    page = request.GET.get('page', 1)

    # Base queryset - show all published products
    products = Product.objects.filter(
        product_status='published'
    ).select_related(
        'vendor',
        'subcategory',
        'subcategory__category'
    ).prefetch_related(
        'productprice_set',
        'variants'
    )

    if query:
        products = products.filter(
            Q(product_name__icontains=query) |
            Q(product_description__icontains=query) |
            Q(subcategory__subcategory_name__icontains=query) |
            Q(subcategory__category__category_name__icontains=query)
        )
    
    # Apply sorting
    if sort == 'price_asc':
        products = products.order_by('base_price')
    elif sort == 'price_desc':
        products = products.order_by('-base_price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    elif sort == 'popular':
        products = products.annotate(
            order_count=Count('orderitem')
        ).order_by('-order_count')
    
    # Add current prices and variant information to products
    for product in products:
        first_variant = product.variants.first()
        if first_variant:
            product.current_price = first_variant.price
            product.stock_quantity = first_variant.stock
        else:
            product.current_price = product.base_price
            product.stock_quantity = 0

    # Pagination
    paginator = Paginator(products, 12)  # Show 12 products per page
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    context = {
        'page_obj': page_obj,
        'query': query,
        'current_sort': sort,
    }
    return render(request, 'search_results.html', context)

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

@login_required
@require_POST
def add_to_wishlist(request, product_id):
    try:
        product = get_object_or_404(Product, id=product_id)
        wishlist_item, created = Wishlist.objects.get_or_create(
            user=request.user,
            product=product
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Product added to wishlist' if created else 'Product is already in wishlist'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
@require_POST
def remove_from_wishlist(request, item_id):
    try:
        wishlist_item = get_object_or_404(Wishlist, id=item_id, user=request.user)
        wishlist_item.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Item removed from wishlist'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def checkout_view(request):
    cart = get_object_or_404(Cart, user=request.user)
    addresses = Address.objects.filter(user=request.user)
    payment_methods = PaymentMethod.objects.filter(user=request.user)
    
    # Calculate totals
    cart_items = cart.cartitem_set.select_related('product', 'variant').all()
    subtotal = sum(item.price_at_time * item.quantity for item in cart_items)
    shipping_cost = 50  # You can make this dynamic
    tax_rate = Decimal('0.18')  # 18% GST
    tax_amount = subtotal * tax_rate
    total = subtotal + shipping_cost + tax_amount
    
    context = {
        'cart': cart,
        'cart_items': cart_items,
        'addresses': addresses,
        'payment_methods': payment_methods,
        'subtotal': subtotal,
        'shipping_cost': shipping_cost,
        'total': total,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
    }
    return render(request, 'accounts/checkout.html', context)

@login_required
@require_POST
def process_checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    address_id = request.POST.get('address_id')
    payment_method_id = request.POST.get('payment_method_id')
    
    try:
        with transaction.atomic():
            # Get address and payment method
            address = Address.objects.get(id=address_id, user=request.user)
            payment_method = PaymentMethod.objects.get(id=payment_method_id, user=request.user)
            
            # Calculate total
            cart_items = cart.cartitem_set.select_related('product', 'variant').all()
            subtotal = sum(item.price_at_time * item.quantity for item in cart_items)
            shipping_cost = 50  # You can make this dynamic
            total_amount = subtotal + shipping_cost
            
            # Create order
            order = Order.objects.create(
                user=request.user,
                total_amount=total_amount,
                shipping_address=address.street_address,
                shipping_city=address.city,
                shipping_state=address.state,
                shipping_zip_code=address.zip_code,
                shipping_country=address.country,
                status='pending'
            )
            
            # Create order items and update stock
            for cart_item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    quantity=cart_item.quantity,
                    price_at_time=cart_item.price_at_time
                )
                
                # Update product stock
                if cart_item.variant:
                    cart_item.variant.stock -= cart_item.quantity
                    cart_item.variant.save()
                else:
                    cart_item.product.stock -= cart_item.quantity
                    cart_item.product.save()
            
            # Clear cart
            cart.cartitem_set.all().delete()
            request.session.pop('cart_count', None)
            
            # Process payment (implement your payment gateway logic here)
            # For now, we'll just mark the order as paid
            order.status = 'paid'
            order.save()
            
            return JsonResponse({
                'status': 'success',
                'order_id': order.id,
                'redirect_url': f'/order-confirmation/{order.id}/'
            })
            
    except Address.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid shipping address'
        }, status=400)
    except PaymentMethod.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid payment method'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def order_detail(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        order_items = OrderItem.objects.filter(order=order).select_related('product')
        
        # Get tracking information
        tracking_info = {
            'order_number': order.id,
            'status': order.status,
            'order_date': order.order_date,
            'estimated_delivery': order.order_date + timezone.timedelta(days=7),
            'current_location': 'In Transit',
            'tracking_number': f'TRK{order.id:08d}',
        }
        
        context = {
            'order': order,
            'order_items': order_items,
            'tracking_info': tracking_info,
            'total_amount': order.total_amount,
            'shipping_address': {
                'street': order.shipping_address,
                'city': order.shipping_city,
                'state': order.shipping_state,
                'zip_code': order.shipping_zip_code,
                'country': order.shipping_country
            }
        }
        return render(request, 'accounts/order_detail.html', context)
    except Order.DoesNotExist:
        messages.error(request, 'Order not found')
        return redirect('user_dashboard')

@login_required
def track_order(request, order_id):
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        order_items = OrderItem.objects.filter(order=order).select_related('product')
        
        # Get tracking information
        tracking_info = {
            'order_number': order.id,
            'status': order.status,
            'order_date': order.order_date,
            'estimated_delivery': order.order_date + timezone.timedelta(days=7),  # Example: 7 days delivery
            'current_location': 'In Transit',  # This should come from your shipping provider
            'tracking_number': f'TRK{order.id:08d}',  # Example tracking number format
        }
        
        context = {
            'order': order,
            'order_items': order_items,
            'tracking_info': tracking_info
        }
        return render(request, 'accounts/track_order.html', context)
    except Order.DoesNotExist:
        messages.error(request, 'Order not found')
        return redirect('user_dashboard')

@login_required
@require_POST
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if order.status == 'pending':
        order.status = 'cancelled'
        order.save()
        return JsonResponse({
            'status': 'success',
            'message': 'Order cancelled successfully'
        })
    return JsonResponse({
        'status': 'error',
        'message': 'Order cannot be cancelled'
    }, status=400)

@login_required
def address_list(request):
    addresses = Address.objects.filter(user=request.user)
    return render(request, 'addresses.html', {
        'addresses': addresses
    })

@login_required
@require_POST
def add_address(request):
    try:
        address = Address.objects.create(
            user=request.user,
            full_name=request.POST.get('full_name'),
            address=request.POST.get('address'),
            city=request.POST.get('city'),
            state=request.POST.get('state'),
            zip_code=request.POST.get('zip_code'),
            country=request.POST.get('country'),
            is_default=request.POST.get('is_default') == 'true'
        )
        return JsonResponse({
            'status': 'success',
            'message': 'Address added successfully',
            'address_id': address.id
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
@require_POST
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    try:
        address.full_name = request.POST.get('full_name')
        address.address = request.POST.get('address')
        address.city = request.POST.get('city')
        address.state = request.POST.get('state')
        address.zip_code = request.POST.get('zip_code')
        address.country = request.POST.get('country')
        address.is_default = request.POST.get('is_default') == 'true'
        address.save()
        return JsonResponse({
            'status': 'success',
            'message': 'Address updated successfully'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
@require_POST
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    address.delete()
    return JsonResponse({
        'status': 'success',
        'message': 'Address deleted successfully'
    })

@login_required
def payment_method_list(request):
    payment_methods = PaymentMethod.objects.filter(user=request.user)
    return render(request, 'payment_methods.html', {
        'payment_methods': payment_methods
    })

@login_required
@require_POST
def add_payment_method(request):
    try:
        # Create payment method without Stripe
        PaymentMethod.objects.create(
            user=request.user,
            brand=request.POST.get('brand'),
            last4=request.POST.get('last4'),
            exp_month=request.POST.get('exp_month'),
            exp_year=request.POST.get('exp_year'),
            is_default=request.POST.get('is_default') == 'true'
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Payment method added successfully'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
@require_POST
def delete_payment_method(request, payment_id):
    payment_method = get_object_or_404(PaymentMethod, id=payment_id, user=request.user)
    try:
        payment_method.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Payment method deleted successfully'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def profile_view(request):
    profile = request.user.profile
    return render(request, 'accounts/profile.html', {
        'profile': profile
    })

@login_required
@require_POST
def update_profile(request):
    profile = request.user.profile
    try:
        profile.phone = request.POST.get('phone')
        profile.order_updates = request.POST.get('order_updates') == 'true'
        profile.promotions = request.POST.get('promotions') == 'true'
        profile.newsletter = request.POST.get('newsletter') == 'true'
        
        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
        
        profile.save()
        return JsonResponse({
            'status': 'success',
            'message': 'Profile updated successfully'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def settings_view(request):
    profile = request.user.profile
    return render(request, 'accounts/settings.html', {
        'profile': profile
    })

@login_required
@require_POST
def notification_settings(request):
    profile = request.user.profile
    try:
        profile.order_updates = request.POST.get('order_updates') == 'true'
        profile.promotions = request.POST.get('promotions') == 'true'
        profile.newsletter = request.POST.get('newsletter') == 'true'
        profile.save()
        return JsonResponse({
            'status': 'success',
            'message': 'Notification settings updated successfully'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=400)

@login_required
def product_list(request):
    # Get filter parameters
    category_id = request.GET.get('category')
    subcategory_id = request.GET.get('subcategory')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort = request.GET.get('sort', 'newest')
    page = request.GET.get('page', 1)

    # Base queryset - show all published products
    products = Product.objects.filter(
        product_status='published'
    ).select_related(
        'vendor',
        'subcategory',
        'subcategory__category'
    ).prefetch_related(
        'productprice_set',
        'variants'
    )

    # Apply filters
    if category_id:
        products = products.filter(subcategory__category_id=category_id)
    if subcategory_id:
        products = products.filter(subcategory_id=subcategory_id)
    if min_price:
        products = products.filter(base_price__gte=min_price)
    if max_price:
        products = products.filter(base_price__lte=max_price)

    # Apply sorting
    if sort == 'price_asc':
        products = products.order_by('base_price')
    elif sort == 'price_desc':
        products = products.order_by('-base_price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    elif sort == 'popular':
        products = products.annotate(
            order_count=Count('orderitem')
        ).order_by('-order_count')
    
    # Add current prices and variant information to products
    for product in products:
        first_variant = product.variants.first()
        if first_variant:
            product.current_price = first_variant.price
            product.stock_quantity = first_variant.stock
        else:
            product.current_price = product.base_price
            product.stock_quantity = 0

    # Pagination
    paginator = Paginator(products, 12)  # Show 12 products per page
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    # Get all categories and subcategories for the filter dropdowns
    categories = Category.objects.all()
    subcategories = Subcategory.objects.all()
    if category_id:
        subcategories = subcategories.filter(category_id=category_id)

    context = {
        'page_obj': page_obj,
        'categories': categories,
        'subcategories': subcategories,
        'selected_category': category_id,
        'selected_subcategory': subcategory_id,
        'min_price': min_price,
        'max_price': max_price,
        'sort': sort,
    }
    return render(request, 'accounts/product_list.html', context)

def about(request):
    return render(request, 'about.html')

def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        try:
            # Send email
            send_mail(
                subject=f'Contact Form: {subject}',
                message=f'From: {name} <{email}>\n\n{message}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.DEFAULT_FROM_EMAIL],
                fail_silently=False,
            )
            messages.success(request, 'Thank you for your message. We will get back to you soon!')
        except Exception as e:
            messages.error(request, 'Sorry, there was an error sending your message. Please try again later.')
        
        return redirect('contact')
    
    return render(request, 'contact.html')

def privacy(request):
    return render(request, 'accounts/privacy.html')

def terms(request):
    return render(request, 'accounts/terms.html')

def faq(request):
    return render(request, 'accounts/faq.html')

def subcategory_products(request, subcategory_id):
    # Get sort parameter
    sort = request.GET.get('sort', 'newest')
    page = request.GET.get('page', 1)
    
    # Get subcategory and its parent category
    subcategory = get_object_or_404(Subcategory.objects.select_related('category'), id=subcategory_id)
    category = subcategory.category
    
    # Base queryset for products
    products = Product.objects.select_related(
        'vendor', 'subcategory'
    ).prefetch_related(
        'productprice_set', 'variants'
    ).filter(
        subcategory_id=subcategory_id,
        product_status='published'
    )
    
    # Apply sorting
    if sort == 'price_asc':
        products = products.order_by('base_price')
    elif sort == 'price_desc':
        products = products.order_by('-base_price')
    elif sort == 'newest':
        products = products.order_by('-created_at')
    elif sort == 'popular':
        products = products.annotate(
            order_count=Count('orderitem')
        ).order_by('-order_count')
    
    # Add current prices and variant information to products
    for product in products:
        first_variant = product.variants.first()
        if first_variant:
            product.current_price = first_variant.price
            product.stock_quantity = first_variant.stock
        else:
            product.current_price = product.base_price
            product.stock_quantity = 0
    
    # Pagination
    paginator = Paginator(products, 12)  # Show 12 products per page
    try:
        products = paginator.page(page)
    except:
        products = paginator.page(1)
    
    context = {
        'products': products,
        'category': category,
        'subcategory': subcategory,
        'current_sort': sort,
    }
    return render(request, 'accounts/category_products.html', context)

@login_required
def wishlist_view(request):
    # Get user's wishlist items with related product data
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related(
        'product',
        'product__vendor'
    ).prefetch_related(
        'product__variants'
    )
    
    context = {
        'wishlist_items': wishlist_items,
    }
    return render(request, 'accounts/wishlist.html', context)

@login_required
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        
        # Verify current password
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return redirect('user_dashboard')
        
        # Check if new password is different from current password
        if current_password == new_password:
            messages.error(request, 'New password must be different from current password.')
            return redirect('user_dashboard')
        
        # Change password
        request.user.set_password(new_password)
        request.user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Password changed successfully.')
        return redirect('user_dashboard')
    
    return redirect('user_dashboard')
