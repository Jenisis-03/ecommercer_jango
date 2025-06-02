from django.shortcuts import get_object_or_404, redirect, render
from .models import Cart
from products.models import Product, Category
from django.db.models import Q

def home(request):
    categories = Category.objects.filter(parent=None)
    category_id = request.GET.get('category')
    subcategory_id = request.GET.get('subcategory')
    search_query = request.GET.get('search')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    products = Product.objects.filter(is_active=True)

    if category_id:
        if subcategory_id:
            products = products.filter(category_id=subcategory_id)
        else:
            category = get_object_or_404(Category, id=category_id)
            subcategories = category.subcategories.all()
            products = products.filter(Q(category=category) | Q(category__in=subcategories))

    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if min_price:
        products = products.filter(price__gte=float(min_price))
    if max_price:
        products = products.filter(price__lte=float(max_price))

    products = products.order_by('-created_at')

    context = {
        'categories': categories,
        'products': products,
        'current_category': category_id,
        'current_subcategory': subcategory_id,
        'search_query': search_query,
        'min_price': min_price,
        'max_price': max_price
    }
    return render(request, 'core/home.html', context)

def add_to_cart(request, product_id):
    if not request.user.is_authenticated:
        return redirect('user_login')
    
    product = get_object_or_404(Product, id=product_id)
    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={'quantity': 1}
    )
    
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    
    return redirect('view_cart')

def view_cart(request):
    if not request.user.is_authenticated:
        return redirect('user_login')
    
    cart_items = Cart.objects.filter(user=request.user)
    total_price = sum(item.total_price for item in cart_items)
    
    context = {
        'cart_items': cart_items,
        'total_price': total_price
    }
    return render(request, 'core/cart.html', context)

def remove_from_cart(request, cart_id):
    if not request.user.is_authenticated:
        return redirect('user_login')
    
    cart_item = get_object_or_404(Cart, id=cart_id, user=request.user)
    cart_item.delete()
    return redirect('view_cart')