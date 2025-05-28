from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib import messages
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from .models import User, Vendor, Product, Order, OrderItem, Category, ProductPrice, Subcategory, Cart, CartItem, ProductVariant, Wishlist, Address
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

logger = logging.getLogger(__name__)

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

def category_products(request, category_id, subcategory_id):
    # Get sort parameter
    sort = request.GET.get('sort', 'newest')
    page = request.GET.get('page', 1)
    
    # Base queryset for products
    products = Product.objects.select_related(
        'vendor', 'subcategory'
    ).prefetch_related(
        'productprice_set'
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
    
    # Add current prices to products
    for product in products:
        product.current_price = product.productprice_set.order_by('-updated_at').first()
    
    # Get category and subcategory info
    category = get_object_or_404(Category, id=category_id)
    subcategory = get_object_or_404(Subcategory, id=subcategory_id)
    
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
            print(f"DEBUG: User created successfully during signup: {user.email} (ID: {user.id})") # Debug print
            messages.success(request, 'Account created successfully')
            return redirect('login')
        except Exception as e:
            print(f"DEBUG: Error creating account during signup: {str(e)}") # Debug print
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
        user_type = request.POST.get('user_type')

        logger.info(f"Login attempt for email: {email}, user_type: {user_type}")
        
        if not email or not password:
            messages.error(request, 'Please provide both email and password')
            return redirect('login')
        
        if user_type == 'admin':
            user = authenticate(request, email=email, password=password)
            if user is not None and user.is_staff:
                # Generate and send OTP
                otp = generate_otp()
                if send_otp_email(email, otp):
                    # Store OTP in session
                    request.session['otp'] = otp
                    request.session['user_id'] = user.id
                    request.session['user_type'] = 'admin'
                    request.session['otp_sent_time'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                    messages.info(request, 'OTP has been sent to your email')
                    return redirect('verify_otp')
                else:
                    messages.error(request, 'Failed to send OTP. Please try again.')
            else:
                messages.error(request, 'Invalid credentials or insufficient permissions.')
                return redirect('login')
        
        elif user_type == 'user':
            user = authenticate(request, email=email, password=password)
            print(f"DEBUG: User authentication result for user type '{user_type}': {user}") # Debug print
            if user is not None:
                # Generate and send OTP
                otp = generate_otp()
                if send_otp_email(email, otp):
                    # Store OTP in session
                    request.session['otp'] = otp
                    request.session['user_id'] = user.id
                    request.session['user_type'] = 'user'
                    request.session['otp_sent_time'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                    messages.info(request, 'OTP has been sent to your email')
                    return redirect('verify_otp')
                else:
                    messages.error(request, 'Failed to send OTP. Please try again.')
            else:
                messages.error(request, 'Invalid login credentials')

        elif user_type == 'vendor':
            try:
                # First check if user exists
                user = User.objects.filter(email=email).first()
                if not user:
                    messages.error(request, 'No account found with this email.')
                    return redirect('login')

                # Then authenticate
                user = authenticate(request, email=email, password=password)
                if user is not None:
                    # Check if user is associated with a vendor
                    try:
                        vendor = Vendor.objects.get(user=user)
                        if vendor.store_status == 'suspended':
                            messages.error(request, 'Your vendor account has been suspended. Please contact support.')
                            return redirect('login')
                            
                        # Generate and send OTP
                        otp = generate_otp()
                        if send_otp_email(email, otp):
                            # Store OTP and vendor data in session
                            request.session['otp'] = otp
                            request.session['user_id'] = user.id
                            request.session['user_type'] = 'vendor'
                            request.session['vendor_id'] = vendor.id
                            request.session['vendor_name'] = vendor.business_name
                            request.session['otp_sent_time'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                            messages.info(request, 'OTP has been sent to your email')
                            return redirect('verify_otp')
                        else:
                            messages.error(request, 'Failed to send OTP. Please try again.')
                    except Vendor.DoesNotExist:
                        messages.error(request, 'No vendor account found for this email. Please sign up as a vendor first.')
                else:
                    messages.error(request, 'Invalid password.')
            except Exception as e:
                print(f"Login error: {str(e)}")  # Debug log
                messages.error(request, 'An error occurred during login. Please try again.')

        else:
            messages.error(request, 'Invalid user type selected')
        
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
def add_to_cart(request, product_id):
    if request.method == 'POST':
        try:
            # Debugging: Print received POST data
            print(f"DEBUG: Add to cart POST data: {request.POST}")
            print(f"DEBUG: Product ID from URL: {product_id}")

            product = get_object_or_404(Product, id=product_id)
            quantity = int(request.POST.get('quantity', 1))
            selected_variant_id = request.POST.get('selected_variant_id')

            print(f"DEBUG: Received quantity: {quantity}") # Debug print
            print(f"DEBUG: Received selected_variant_id: {selected_variant_id}") # Debug print

            # Get or create cart for the user
            cart, created = Cart.objects.get_or_create(user=request.user)

            if selected_variant_id:
                # If a variant is selected, get the variant and use its price and stock
                variant = get_object_or_404(ProductVariant, id=selected_variant_id, product=product)
                # Check if the exact variant is already in cart
                cart_item, created = CartItem.objects.get_or_create(
                    cart=cart,
                    product=product, # Keep product reference
                    variant=variant, # Add variant reference
                    defaults={'quantity': quantity, 'price_at_time': variant.price} # Use variant price
                )
                if not created:
                    cart_item.quantity += quantity
                    # Optional: update price_at_time if you want to reflect price changes
                    # cart_item.price_at_time = variant.price
                    cart_item.save()

                messages.success(request, f'{product.product_name} ({variant.color}/{variant.size}) added to cart!')
            else:
                # If no variant is selected (for products without variants), use base price/default logic
                # Check if product is already in cart (for non-variant products)
                # Assuming products without variants don't have ProductPrice or use base_price
                cart_item, created = CartItem.objects.get_or_create(
                    cart=cart,
                    product=product,
                    variant=None, # Explicitly set variant to None
                    defaults={'quantity': quantity, 'price_at_time': product.base_price} # Use base price
                )

                if not created:
                    cart_item.quantity += quantity
                     # Optional: update price_at_time if you want to reflect price changes
                    # cart_item.price_at_time = product.base_price
                    cart_item.save()

                messages.success(request, f'{product.product_name} added to cart!')

            # Redirect to view cart regardless of variant selection
            return redirect('view_cart')

        except Product.DoesNotExist:
            messages.error(request, 'Product not found.')
        except ProductVariant.DoesNotExist:
             messages.error(request, 'Product variant not found.')
        except ValueError:
             messages.error(request, 'Invalid quantity.')
        except Exception as e:
            messages.error(request, f'Error adding to cart: {str(e)}')

    # If not a POST request or an error occurred, redirect to product detail page
    # return redirect('product_detail', product_id=product_id) # Or redirect home if product_id is not available
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
def add_to_wishlist(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        wishlist_item, created = Wishlist.objects.get_or_create(
            user=request.user,
            product=product
        )
        if not created:
            messages.info(request, 'Product is already in your wishlist')
        else:
            messages.success(request, 'Product added to wishlist')
    return redirect('product_detail', product_id=product_id)

@login_required
def remove_from_wishlist(request, wishlist_id):
    if request.method == 'POST':
        wishlist_item = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
        wishlist_item.delete()
        messages.success(request, 'Product removed from wishlist')
    return redirect('user_dashboard')

@login_required
def add_address(request):
    if request.method == 'POST':
        address = Address.objects.create(
            user=request.user,
            address_type=request.POST.get('address_type'),
            street_address=request.POST.get('street_address'),
            city=request.POST.get('city'),
            state=request.POST.get('state'),
            zip_code=request.POST.get('zip_code'),
            country=request.POST.get('country')
        )
        messages.success(request, 'Address added successfully')
    return redirect('user_dashboard')

@login_required
def delete_address(request, address_id):
    if request.method == 'POST':
        address = get_object_or_404(Address, id=address_id, user=request.user)
        address.delete()
        messages.success(request, 'Address deleted successfully')
    return redirect('user_dashboard')

@login_required
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect')
        elif new_password != confirm_password:
            messages.error(request, 'New passwords do not match')
        else:
            request.user.set_password(new_password)
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, 'Password changed successfully')
    return redirect('user_dashboard')

@login_required
def update_vendor_profile(request):
    if request.method == 'POST':
        vendor = get_object_or_404(Vendor, id=request.session['vendor_id'])
        vendor.business_name = request.POST.get('business_name')
        vendor.contact_email = request.POST.get('contact_email')
        vendor.shop_address = request.POST.get('shop_address')
        vendor.description = request.POST.get('description')
        vendor.save()
        messages.success(request, 'Profile updated successfully')
    return redirect('vendor_dashboard')

@login_required
def update_vendor_settings(request):
    if request.method == 'POST':
        vendor = get_object_or_404(Vendor, id=request.session['vendor_id'])
        vendor.email_notifications = request.POST.get('email_notifications') == 'on'
        vendor.order_notifications = request.POST.get('order_notifications') == 'on'
        vendor.store_status = request.POST.get('store_status')
        vendor.save()
        messages.success(request, 'Settings updated successfully')
    return redirect('vendor_dashboard')

@login_required
def update_order_status(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if new_status in ['pending', 'processing', 'shipped', 'delivered', 'cancelled']:
            order.status = new_status
            order.save()
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def view_wishlist(request):
    wishlist_items = Wishlist.objects.filter(user=request.user).select_related('product')
    context = {
        'wishlist_items': wishlist_items,
    }
    return render(request, 'accounts/wishlist.html', context)
