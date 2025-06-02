from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_protect
from django.core.paginator import Paginator
from django.db.models import Prefetch, Sum
from .forms import VendorSignUpForm, VendorLoginForm
from .models import Vendor
from products.models import Product, Category
from orders.models import Order
from django.contrib.auth import logout

@csrf_protect
def vendor_signup(request):
    if request.method == 'POST':
        form = VendorSignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_vendor = True
            user.save()
            vendor = Vendor.objects.create(user=user, shop_name=form.cleaned_data['shop_name'])
            login(request, user)
            return redirect('vendor_dashboard')
    else:
        form = VendorSignUpForm()
    return render(request, 'vendors/signup.html', {'form': form})

@csrf_protect
def vendor_login(request):
    if request.method == 'POST':
        form = VendorLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_vendor:
                login(request, user)
                return redirect('vendor_dashboard')
    else:
        form = VendorLoginForm()
    return render(request, 'vendors/login.html', {'form': form})

@login_required
def vendor_dashboard(request):
    if not request.user.is_authenticated or not request.user.is_vendor:
        return redirect('vendor_login')
    
    vendor = request.user.vendor
    products = Product.objects.filter(vendor=vendor)
    low_stock_count = products.filter(quantity__lte=5).count()
    
    # Optimize query with prefetch_related
    recent_orders = Order.objects.filter(
        items__product__vendor=vendor
    ).prefetch_related(
        'items__product'
    ).distinct().order_by('-ordered_at')[:5]
    
    # Calculate earnings with aggregation
    delivered_orders = Order.objects.filter(
        items__product__vendor=vendor,
        status='Delivered'
    ).annotate(
        vendor_total=Sum('items__price')
    )
    total_earnings = sum(order.vendor_total for order in delivered_orders)
    
    # Calculate pending payouts
    pending_orders = Order.objects.filter(
        items__product__vendor=vendor,
        items__vendor_paid=False
    ).annotate(
        vendor_total=Sum('items__price')
    )
    pending_payouts = sum(order.vendor_total for order in pending_orders)
    
    context = {
        'products': products,
        'low_stock_count': low_stock_count,
        'recent_orders': recent_orders,
        'total_earnings': total_earnings,
        'pending_payouts': pending_payouts,
    }
    return render(request, 'vendors/dashboard.html', context)

@login_required
@csrf_protect
def edit_product(request, product_id):
    if not request.user.is_vendor:
        return redirect('home')
    
    product = get_object_or_404(Product, id=product_id, vendor__user=request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')
        category_id = request.POST.get('category')
        
        try:
            category = Category.objects.get(id=category_id)
            
            product.title = title
            product.description = description
            product.price = price
            product.quantity = quantity
            product.category = category
            
            if 'image' in request.FILES:
                product.image = request.FILES['image']
            
            product.full_clean()
            product.save()
            
            messages.success(request, 'Product updated successfully')
            return redirect('vendor_dashboard')
            
        except (Category.DoesNotExist, ValidationError) as e:
            messages.error(request, str(e))
    
    categories = Category.objects.all()
    return render(request, 'vendors/edit_product.html', {
        'product': product,
        'categories': categories
    })

@login_required
def update_order_status(request, order_id):
    if not request.user.is_vendor:
        return redirect('home')
    
    order = get_object_or_404(Order, id=order_id)
    vendor_items = order.get_vendor_items(request.user.vendor)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        tracking_number = request.POST.get('tracking_number')
        estimated_delivery = request.POST.get('estimated_delivery')
        
        if status:
            order.status = status
        if tracking_number:
            order.tracking_number = tracking_number
        if estimated_delivery:
            order.estimated_delivery = estimated_delivery
        
        order.save()
        
        # Send email notification to customer
        context = {
            'order': order,
            'status': status,
            'tracking_number': tracking_number,
            'estimated_delivery': estimated_delivery
        }
        email_html = render_to_string('orders/email/status_update.html', context)
        send_mail(
            subject=f'Order #{order.id} Status Update',
            message='',
            html_message=email_html,
            from_email='noreply@ecommerce.com',
            recipient_list=[order.user.email]
        )
        
        messages.success(request, 'Order status updated successfully')
        return redirect('vendor_orders')
    
    return render(request, 'vendors/update_order.html', {
        'order': order,
        'vendor_items': vendor_items
    })

@login_required
def vendor_settings(request):
    if not request.user.is_vendor:
        return redirect('home')
    
    vendor = request.user.vendor
    
    if request.method == 'POST':
        # Update vendor information
        vendor.shop_name = request.POST.get('shop_name')
        vendor.business_email = request.POST.get('business_email')
        vendor.business_phone = request.POST.get('business_phone')
        vendor.business_address = request.POST.get('business_address')
        vendor.store_description = request.POST.get('store_description')
        vendor.tax_id = request.POST.get('tax_id')
        
        if 'logo' in request.FILES:
            vendor.logo = request.FILES['logo']
        if 'banner' in request.FILES:
            vendor.banner = request.FILES['banner']
            
        vendor.save()
        messages.success(request, 'Store settings updated successfully')
        return redirect('vendor_settings')
    
    return render(request, 'vendors/settings.html', {'vendor': vendor})

@login_required
def vendor_orders(request):
    if not request.user.is_vendor:
        return redirect('home')
    
    orders = Order.objects.filter(items__product__vendor=request.user.vendor).distinct()
    return render(request, 'vendors/orders.html', {'orders': orders})

@login_required
def delete_product(request, product_id):
    if not request.user.is_vendor:
        return redirect('home')
    
    product = get_object_or_404(Product, id=product_id, vendor__user=request.user)
    product.delete()
    return redirect('vendor_dashboard')


@login_required
def vendor_logout(request):
    if request.user.is_vendor:
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
    return redirect('home')

def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Your email has been verified. You can now login.')
        return redirect('vendor_login')
    else:
        messages.error(request, 'The verification link was invalid or has expired.')
        return redirect('home')

def email_verification_sent(request):
    return render(request, 'vendors/email_verification_sent.html')

# Update the vendor_signup view to include email verification
def vendor_signup(request):
    if request.method == 'POST':
        form = VendorSignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_vendor = True
            user.is_active = False  # User won't be able to login until email is verified
            user.save()
            vendor = Vendor.objects.create(user=user, shop_name=form.cleaned_data['shop_name'])

            # Generate verification token
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verification_url = request.build_absolute_uri(
                reverse('vendor_verify_email', kwargs={'uidb64': uid, 'token': token})
            )

            # Send verification email
            context = {
                'user': user,
                'verification_url': verification_url,
            }
            email_html = render_to_string('vendors/email/verification.html', context)
            send_mail(
                'Verify your email address',
                '',
                'noreply@ecommerce.com',
                [user.email],
                html_message=email_html,
                fail_silently=False,
            )

            return redirect('vendor_email_verification_sent')
    else:
        form = VendorSignUpForm()
    return render(request, 'vendors/signup.html', {'form': form})