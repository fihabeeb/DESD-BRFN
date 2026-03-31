from django.shortcuts import render, get_object_or_404, redirect
from mainApp.decorators import customer_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
import stripe
from datetime import date, timedelta, datetime
from customers.models import Cart
from mainApp.models import Address
from orders.models import Order, OrderItem
from decimal import ROUND_HALF_UP
from django.contrib.auth import get_user_model 


User = get_user_model()


@login_required
def checkout(request):

    try:
        cart = request.user.customer_profile.cart
    except (AttributeError, Cart.DoesNotExist):
        return redirect('mainApp:products:product_list')

    if cart.items.count() == 0:
        return redirect('mainApp:products:product_list')
    
    addresses = request.user.addresses.all()
    default_address = addresses.filter(
        address_type='shipping', is_default=True
        ).first() or addresses.filter(is_default=True).first()
    
    if not default_address and addresses.exists():
        # Edge case: addresses exist but none is default — promote the first one
        default_address = addresses.order_by('-created_at').first()
        default_address.is_default = True
        default_address.save()
    
    # Calculate totals
    total = cart.total_amount()
    
    min_delivery_date = (date.today()+ timedelta(days=2)).strftime('%Y-%m-%d')

    context = {
        'cart': cart,
        'cart_items': cart.items.select_related('product').all(),
        'total': total,
        'addresses': addresses,
        'default_address': default_address,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
        'min_delivery_date': min_delivery_date,
    }
    
    return render(request, "orders/checkout.html", context)



@login_required
def create_checkout_session(request):
    """Create Stripe Checkout Session"""
    
    if request.method != 'POST':
        return redirect('mainApp:orders:checkout')
    
    # Get address from form
    address_id = request.POST.get('address_id')
    delivery_date = None
    delivery_date_str = request.POST.get('delivery_date')
    if delivery_date_str:
        delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d').date()
        if delivery_date < date.today() + timedelta(days=2):
            return JsonResponse({'error': 'Delivery date must be at least 48 hours from now'}, status=400)
    
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
        price_in_cents = int(cart_item.product.price * 100)#.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
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
    
    try:
        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=request.build_absolute_uri(reverse('mainApp:orders:success')) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri(reverse('mainApp:orders:cancel')),
            customer_email=request.user.email,
            metadata={
                'user_id': request.user.id,
                'address_id': address.id,
                'delivery_date': delivery_date or '',
            }
        )
        
        # Create order immediately so it appears in the DB before the webhook fires.
        # The webhook will update status to 'confirmed', deduct stock, and clear the cart.
        order = Order.objects.create(
            customer=request.user.customer_profile,
            user=request.user,
            stripe_session_id=checkout_session.id,
            total_amount=cart.total_amount(),
            shipping_address_id=address,
            delivery_date=delivery_date,
            status='pending'
        )
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
        return JsonResponse({'error': f'An error occurred: {e}'}, status=400)

@login_required
def success(request):
    """Handle successful payment. Confirms the order if webhook hasn't done so yet."""
    session_id = request.GET.get('session_id')
    order = Order.objects.filter(stripe_session_id=session_id).first()

    if order and order.status == 'pending':
        # Webhook hasn't fired yet (common in local dev). Verify with Stripe and confirm.
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                order.stripe_payment_intent_id = session.payment_intent
                order.status = 'confirmed'
                order.save()

                # Deduct stock
                for item in order.items.all():
                    if item.product:
                        item.product.deduct_stock(item.quantity)

                # Clear cart
                try:
                    order.user.customer_profile.cart.items.all().delete()
                except Exception:
                    pass
        except stripe.error.StripeError:
            pass

    return render(request, 'orders/success.html', {'order': order})
    

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

        existing_order = Order.objects.filter(stripe_session_id=session['id']).first()

        # If already confirmed (webhook fired twice), do nothing
        if existing_order and existing_order.status == 'confirmed':
            return HttpResponse(status=200)

        try:
            if existing_order:
                # Order was pre-created at checkout; confirm it and finalise
                order = existing_order
                order.stripe_payment_intent_id = session.get('payment_intent')
                order.status = 'confirmed'
                order.save()
            else:
                # Fallback: order wasn't pre-created, create it now
                metadata = session.get('metadata', {})
                user_id = metadata.get('user_id')
                address_id = metadata.get('address_id')
                delivery_date_str = metadata.get('delivery_date')
                user = User.objects.get(id=user_id)
                address = Address.objects.get(id=address_id)
                cart = user.customer_profile.cart
                order = Order.objects.create(
                    customer=user.customer_profile,
                    user=user,
                    stripe_session_id=session['id'],
                    stripe_payment_intent_id=session.get('payment_intent'),
                    total_amount=cart.total_amount(),
                    shipping_address_id=address,
                    delivery_date=delivery_date_str or None,
                    status='confirmed',
                )
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

            # Deduct stock and clear cart
            for item in order.items.all():
                if item.product:
                    item.product.deduct_stock(item.quantity)

            order.user.customer_profile.cart.items.all().delete()

        except Exception as e:
            print(f"Webhook order processing failed: {e}")
            return HttpResponse(status=500)
    return HttpResponse(status=200)


#TODO:
# bug 
# move all post payment logic to stripe webhook. 

# TODO:

