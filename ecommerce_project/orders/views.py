from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from .models import Order, OrderItem
from core.models import Cart
import stripe
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

stripe.api_key = settings.STRIPE_SECRET_KEY

@csrf_protect
@require_POST
def process_payment(request):
    try:
        data = json.loads(request.body)
        payment_method_id = data['payment_method_id']
        address = data['address']

        # Calculate the order amount
        cart_items = Cart.objects.filter(user=request.user)
        amount = sum(item.product.price * item.quantity for item in cart_items)
        
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            payment_method=payment_method_id,
            amount=int(amount * 100),  # Convert to cents
            currency='usd',
            confirmation_method='manual',
            confirm=True,
        )

        if intent.status == 'requires_action':
            return JsonResponse({
                'requires_action': True,
                'payment_intent_client_secret': intent.client_secret
            })
        elif intent.status == 'succeeded':
            # Create order and clear cart
            order = Order.objects.create(
                user=request.user,
                total_amount=amount,
                shipping_address=address,
                payment_id=intent.id
            )
            
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
            
            cart_items.delete()
            
            return JsonResponse({
                'success_url': reverse('order_confirmation', args=[order.id])
            })
    except Exception as e:
        return JsonResponse({'error': str(e)})

@login_required
def checkout(request):
    try:
        with transaction.atomic():
            if request.method == 'POST':
                carts = Cart.objects.filter(user=request.user)
                if not carts.exists():
                    return redirect('view_cart')

                order_items = []
                total = 0
                for cart in carts:
                    if not cart.product.has_sufficient_stock(cart.quantity):
                        messages.error(request, f'Not enough stock for {cart.product.title}')
                        return redirect('view_cart')
                    
                    order_item = OrderItem.objects.create(
                        product=cart.product,
                        quantity=cart.quantity,
                        price=cart.product.price
                    )
                    order_items.append(order_item)
                    total += cart.product.price * cart.quantity
                    
                    cart.product.quantity -= cart.quantity
                    cart.product.save()

                order = Order.objects.create(
                    user=request.user,
                    total_price=total,
                    shipping_address=request.POST.get('address', request.user.address)
                )
                order.items.set(order_items)

                try:
                    context = {
                        'order': order,
                        'items': order_items,
                        'user': request.user
                    }
                    email_html = render_to_string('orders/email/confirmation.html', context)
                    send_mail(
                        subject=f'Order Confirmation #{order.id}',
                        message='',
                        html_message=email_html,
                        from_email='noreply@ecommerce.com',
                        recipient_list=[request.user.email],
                        fail_silently=False
                    )
                except Exception as e:
                    messages.warning(request, 'Order placed but confirmation email could not be sent')

                carts.delete()
                return redirect('order_confirmation')

    except Exception as e:
        messages.error(request, 'An error occurred during checkout. Please try again.')
        return redirect('view_cart')

    return render(request, 'orders/checkout.html')

def order_confirmation(request):
    orders = Order.objects.filter(user=request.user).order_by('-ordered_at')[:5]
    return render(request, 'orders/confirmation.html', {'orders': orders})

def order_history(request):
    if not request.user.is_authenticated:
        return redirect('user_login')
    
    orders_list = Order.objects.filter(user=request.user).order_by('-ordered_at')
    paginator = Paginator(orders_list, 10)
    page = request.GET.get('page')
    orders = paginator.get_page(page)
    
    return render(request, 'orders/history.html', {'orders': orders})