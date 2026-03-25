from django.shortcuts import render, get_object_or_404, redirect
from mainApp.decorators import customer_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
import stripe

from customers.models import Cart
from mainApp.models import Address
from orders.models import Order, OrderItem


@login_required
def checkout(request):

    try:
        cart = request.user.customer_profile.cart
    except (AttributeError, Cart.DoesNotExist):
        return redirect('products:product_list')

    if cart.items.count() == 0:
        return redirect('products:product_list')
    
    addresses = request.user.addresses.all()
    default_address = addresses.filter(is_default=True).first()
    
    # Calculate totals
    subtotal = cart.subtotal()
    commission = cart.commission()
    total = subtotal + commission
    
    context = {
        'cart': cart,
        'cart_items': cart.items.select_related('product').all(),
        'subtotal': subtotal,
        'commission': commission,
        'total': total,
        'addresses': addresses,
        'default_address': default_address,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    }
    
    return render(request, "orders/checkout.html", context)



@login_required
def create_checkout_session(request):
    """Create Stripe Checkout Session"""
    
    if request.method != 'POST':
        return redirect('orders:checkout')
    
    # Get address from form
    address_id = request.POST.get('address_id')
    delivery_date = request.POST.get('delivery_date')
    
    try:
        address = Address.objects.get(id=address_id, user=request.user)
    except Address.DoesNotExist:
        return JsonResponse({'error': 'Please select a valid address'}, status=400)
    
    # Get cart
    try:
        cart = request.user.customer_profile.cart
    except (AttributeError, Cart.DoesNotExist):
        return JsonResponse({'error': 'Cart not found'}, status=400)
    
    if cart.items.count() == 0:
        return JsonResponse({'error': 'Cart is empty'}, status=400)
    
    # Build line items for Stripe
    line_items = []
    
    for cart_item in cart.items.select_related('product').all():
        price_in_cents = int(cart_item.product.price * 100)
        line_items.append({
            'price_data': {
                'currency': 'gbp',
                'product_data': {
                    'name': cart_item.product.name,
                    'description': cart_item.product.description[:100] if cart_item.product.description else "",
                },
                'unit_amount': price_in_cents,
            },
            'quantity': cart_item.quantity,
        })
    
    # Add commission as a line item
    commission_in_cents = int(cart.commission() * 100)
    if commission_in_cents > 0:
        line_items.append({
            'price_data': {
                'currency': 'gbp',
                'product_data': {
                    'name': 'Network Commission (5%)',
                    'description': 'Supports the Bristol Regional Food Network',
                },
                'unit_amount': commission_in_cents,
            },
            'quantity': 1,
        })
    
    try:
        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.build_absolute_uri(reverse('orders:success')) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri(reverse('orders:cancel')),
            customer_email=request.user.email,
            metadata={
                'user_id': request.user.id,
                'address_id': address.id,
                'delivery_date': delivery_date or '',
            }
        )
        
        # Create order record
        order = Order.objects.create(
            customer=request.user.customer_profile,
            user=request.user,
            stripe_session_id=checkout_session.id,
            subtotal=cart.subtotal(),
            commission=cart.commission(),
            total_amount=cart.total_amount(),
            shipping_address=address.full_address,
            shipping_address_id=address.id,
            delivery_date=delivery_date or None,
            status='pending'
        )
        
        # Create order items from cart items
        for cart_item in cart.items.select_related('product').all():
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                producer=cart_item.product.producer,
                product_name=cart_item.product.name,
                product_price=cart_item.product.price,
                quantity=cart_item.quantity,
                unit=cart_item.product.unit,
            )
        
        return JsonResponse({'sessionId': checkout_session.id})
        
    except stripe.error.StripeError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'An error occurred'}, status=400)

@login_required
def success(request):
    """Handle successful payment"""
    session_id = request.GET.get('session_id')
    
    if session_id:
        try:
            # Retrieve session from Stripe
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            
            # Update order status
            order = Order.objects.filter(stripe_session_id=session_id).first()
            if order:
                order.status = 'processing'
                order.stripe_payment_intent_id = checkout_session.payment_intent
                order.save()
                
                # Clear the cart
                cart = request.user.customer_profile.cart
                cart.items.all().delete()
                
                # Store order in session for success page
                request.session['last_order_id'] = order.id
                
        except stripe.error.StripeError:
            pass
    
    return render(request, 'orders/success.html')

def cancel(request):
    """Handle cancelled payment"""
    return render(request, 'orders/cancel.html')

@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Update order status
        order = Order.objects.filter(stripe_session_id=session['id']).first()
        if order:
            order.status = 'confirmed'
            order.stripe_payment_intent_id = session['payment_intent']
            order.save()
            
            # Reduce stock for ordered items
            for item in order.items.all():
                if item.product:
                    item.product.deduct_stock(item.quantity)
    
    return HttpResponse(status=200)