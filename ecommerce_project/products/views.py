from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Product
from vendors.models import Vendor
from django.core.exceptions import PermissionDenied

@login_required
def upload_product(request):
    if not request.user.is_vendor:
        raise PermissionDenied("Only vendors can upload products")
    
    categories = Category.objects.all()
    
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity')
        category_id = request.POST.get('category')
        image = request.FILES.get('image')
        
        if not all([title, description, price, quantity, category_id, image]):
            messages.error(request, 'Please fill all required fields')
            return render(request, 'products/upload.html', {'categories': categories})
        
        try:
            vendor = Vendor.objects.get(user=request.user)
            category = Category.objects.get(id=category_id)
            
            product = Product.objects.create(
                vendor=vendor,
                category=category,
                title=title,
                description=description,
                price=price,
                quantity=quantity,
                image=image
            )
            messages.success(request, 'Product uploaded successfully')
            return redirect('product_detail', product_id=product.id)
            
        except Exception as e:
            messages.error(request, 'Error uploading product')
            return render(request, 'products/upload.html', {'categories': categories})
    
    return render(request, 'products/upload.html', {'categories': categories})

def product_list(request):
    products = Product.objects.all().order_by('-created_at')
    return render(request, 'products/list.html', {'products': products})

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, 'products/detail.html', {'product': product})
