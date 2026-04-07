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
from orders.models import OrderPayment, OrderProducer, OrderItem
from decimal import ROUND_HALF_UP
from django.contrib.auth import get_user_model 
from django.utils import timezone
import json


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

    producer_groups = cart.get_items_by_producer()

    now = timezone.now()
    for group in producer_groups.values():
        min_delivery = now + timedelta(hours=group['lead_time_hours'])
        group['min_delivery_date'] = min_delivery.date().isoformat()
        group['min_delivery_display'] = min_delivery.strftime('%d %b %Y')

    context = {
        'cart': cart,
        'cart_items': cart.items.select_related('product').all(),
        'total': total,
        'addresses': addresses,
        'default_address': default_address,
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
        'min_delivery_date': (date.today() + timedelta(days=2)).strftime('%Y-%m-%d'),
        'producer_groups': producer_groups,
    }
    
    return render(request, "orders/checkout.html", context)



@login_required
def create_checkout_session(request):
    """Create Stripe Checkout Session"""
    
    if request.method != 'POST':
        return redirect('mainApp:orders:checkout')

    cart = request.user.customer_profile.cart
    now  = timezone.now()
    address_id = request.POST.get('address_id')
    global_delivery_notes = request.POST.get('global_delivery_notes', '')

    producer_groups = cart.get_items_by_producer()

    # Validate delivery date per producer
    delivery_dates = {}   # { producer_id: date }
    errors = []

    for producer_id, group in producer_groups.items():
        date_str = request.POST.get(f'delivery_date_{producer_id}')
        if not date_str:
            errors.append(f"Please select a delivery date for {group['business_name']}.")
            continue

        try:
            delivery_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            errors.append(f"Invalid delivery date for {group['business_name']}.")
            continue

        lead_hours = group['lead_time_hours']
        min_delivery = (now + timedelta(hours=lead_hours)).date()

        if delivery_date < min_delivery:
            errors.append(
                f"{group['business_name']} requires at least {lead_hours}h notice. "
                f"Earliest available date is {min_delivery.strftime('%d %b %Y')}."
            )
            continue

        delivery_dates[producer_id] = delivery_date

    if errors:
        return JsonResponse({'error': errors}, status=400)
    
    # Validate address
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
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,  # Just the products
            mode='payment',
            success_url=request.build_absolute_uri(reverse('mainApp:orders:success')) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=request.build_absolute_uri(reverse('mainApp:orders:cancel')),
            customer_email=request.user.email,
            metadata={
                'user_id': request.user.id,
                'user_name': request.user.get_full_name(),
                'user_email': request.user.email,
                'user_phone_number': request.user.phone_number,
                'address_id': address.id,
                'global_delivery_notes': global_delivery_notes,
                'cart_id': request.user.customer_profile.cart.id,
                'item_count': str(cart.item_count()),
                'item_total': str(cart.total_amount()),
                'total_producers_involved': str(len(producer_groups)),
                # 'delivery_dates': json.dumps({
                #     str(pid): d.isoformat()
                #     for pid, d in delivery_dates.items()
                # }),
            }
        )
        
        # Create OrderPayment (customer payment)
        payment = OrderPayment.objects.create(
            customer=request.user.customer_profile,
            user=request.user,
            stripe_session_id=checkout_session.id,
            total_amount=cart.total_amount(),  # Just product total
            shipping_address=address,
            global_delivery_notes=global_delivery_notes,
            payment_status='pending'
        )
        
        # Create OrderProducer for each producer (commission calculated here)
        producer_groups = cart.get_items_by_producer()
        for producer_id, group in producer_groups.items():
            delivery_date = delivery_dates.get(producer_id)
            customer_note = request.POST.get(f'customer_note_{producer_id}', '')
            
            producer_order = OrderProducer.objects.create(
                payment=payment,
                producer=group['producer'],
                producer_subtotal=group['subtotal'],  # What customer paid for these items
                order_status='pending',
                customer_note=customer_note,
                delivered_by=delivery_date,
            )
            
            for cart_item in group['items']:
                OrderItem.objects.create(
                    producer_order=producer_order,
                    product=cart_item.product,
                    product_name=cart_item.product.name,
                    product_price=cart_item.product.price,
                    quantity=cart_item.quantity,
                    unit=cart_item.product.unit,
                )
        
        return JsonResponse({'sessionId': checkout_session.id})
        
    except stripe.error.StripeError as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def success(request):
    """Handle successful payment. Confirms the order if webhook hasn't done so yet."""
    session_id = request.GET.get('session_id')
    order = OrderPayment.objects.filter(stripe_session_id=session_id).first()

    # if order and order.status == 'pending':
    #     # Webhook hasn't fired yet (common in local dev). Verify with Stripe and confirm.
    #     try:
    #         session = stripe.checkout.Session.retrieve(session_id)
    #         if session.payment_status == 'paid':
    #             order.stripe_payment_intent_id = session.payment_intent
    #             order.status = 'confirmed'
    #             order.save()

    #             # Deduct stock
    #             for item in order.items.all():
    #                 if item.product:
    #                     item.product.deduct_stock(item.quantity)

    #             # Clear cart
    #             try:
    #                 order.user.customer_profile.cart.items.all().delete()
    #             except Exception:
    #                 pass
    #     except stripe.error.StripeError:
    #         pass

    return render(request, 'orders/success.html', {'order': order})
    

def cancel(request):
    """Handle cancelled payment"""
    return render(request, 'orders/cancel.html')

@csrf_exempt
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    print("webhook received")

    # delivery_dates = json.loads(metadata.get('delivery_dates', '{}'))
    
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

        existing_payment = OrderPayment.objects.filter(stripe_session_id=session['id']).first()

        # If already confirmed (webhook fired twice), do nothing
        if existing_payment and existing_payment.payment_status == 'confirmed':
            return HttpResponse(status=200)

        try:
            if existing_payment:
                # Order was pre-created at checkout; confirm it and finalise
                payment = existing_payment
                payment.stripe_payment_intent_id = session.get('payment_intent')
                payment.payment_status = 'paid'
                payment.save()
            else:
                # Fallback: order wasn't pre-created, create it now
                # this should never run tbh.
                metadata = session.get('metadata', {})
                user_id = metadata.get('user_id')
                address_id = metadata.get('address_id')
                user = User.objects.get(id=user_id)
                address = Address.objects.get(id=address_id)
                cart = user.customer_profile.cart
                payment = OrderPayment.objects.create(
                    customer=user.customer_profile,
                    user=user,
                    stripe_session_id=session['id'],
                    stripe_payment_intent_id=session.get('payment_intent'),
                    total_amount=cart.total_amount(),
                    shipping_address_id=address,
                    status='paid',
                )

            # order_producers=OrderProducer.objects.filter(payment=payment.id)
            
            # if order_producers:
            #     for order_producer in order_producers:
            #         order_producer.order_status="confirmed"
            #         order_producer.save()

            # Deduct stock and clear cart
            for item in payment.user.customer_profile.cart.items.all():
                if item.product:
                    item.product.deduct_stock(item.quantity)

            payment.user.customer_profile.cart.items.all().delete()

        except Exception as e:
            print(f"Webhook order processing failed: {e}")
            return HttpResponse(status=500)
    return HttpResponse(status=200)



