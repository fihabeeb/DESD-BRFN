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
from orders.models import (
    OrderPayment, OrderProducer, OrderItem,
    RecurringOrder, RecurringOrderItem, OrderInstance, OrderInstanceItem,
)
from decimal import ROUND_HALF_UP
from django.contrib.auth import get_user_model 
from django.utils import timezone
import json
from django.db import transaction
from django.db import models


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
    special_instructions = request.POST.get('special_instructions', '')  # TC-017

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

    # Re-check stock for all cart items before creating a Stripe session
    from products.models import Product as ProductModel
    stock_errors = []
    for cart_item in cart.items.select_related('product').all():
        if cart_item.product is None:
            continue
        # Re-fetch current stock from DB to catch concurrent changes
        current_stock = ProductModel.objects.filter(id=cart_item.product.id).values_list('stock_quantity', flat=True).first()
        if current_stock is None or cart_item.quantity > current_stock:
            stock_errors.append(
                f'"{cart_item.product_name}" only has {current_stock or 0} units in stock but you requested {cart_item.quantity}.'
            )
    if stock_errors:
        return JsonResponse({'error': stock_errors}, status=400)

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
        # TC-017: detect community group accounts for bulk order flagging
        is_community_group = (
            hasattr(request.user, 'role') and
            request.user.role == 'community_member'
        )

        # TC-018: recurring order for restaurant users
        make_recurring = request.POST.get('make_recurring') == 'on'
        recurrence = request.POST.get('recurrence', 'weekly')
        recurrence_day = request.POST.get('recurrence_day', 'monday')
        delivery_day = request.POST.get('delivery_day', 'monday')

        with transaction.atomic():
            # Create OrderPayment (customer payment)
            payment = OrderPayment.objects.create(
                # customer=request.user.customer_profile,
                user=request.user,
                stripe_session_id=checkout_session.id,
                total_amount=cart.total_amount(),  # Just product total
                shipping_address=address,
                global_delivery_notes=global_delivery_notes,
                special_instructions=special_instructions,  # TC-017
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
                    is_bulk_order=is_community_group,  # TC-017
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

            # TC-018: create RecurringOrder for restaurant users who opted in
            if make_recurring and hasattr(request.user, 'role') and request.user.role == 'restaurant':
                from orders.models import RecurringOrder, RecurringOrderItem
                recurring = RecurringOrder.objects.create(
                    customer=request.user,
                    status='active',
                    recurrence=recurrence,
                    recurrence_day=recurrence_day,
                    delivery_day=delivery_day,
                )
                for cart_item in cart.items.select_related('product').all():
                    RecurringOrderItem.objects.create(
                        recurring_order=recurring,
                        product=cart_item.product,
                        producer=cart_item.product.producer if cart_item.product else None,
                        product_name=cart_item.product.name if cart_item.product else cart_item.product_name,
                        quantity=cart_item.quantity,
                        unit=cart_item.product.unit if cart_item.product else '',
                    )

        return JsonResponse({'sessionId': checkout_session.id})
        
    except stripe.error.StripeError as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def success(request):
    """Handle successful payment."""
    session_id = request.GET.get('session_id')
    order = OrderPayment.objects.filter(stripe_session_id=session_id).first()

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

        # If already paid (webhook fired twice), do nothing
        if existing_payment and existing_payment.payment_status == 'paid':
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
                    # customer=user.customer_profile,
                    user=user,
                    stripe_session_id=session['id'],
                    stripe_payment_intent_id=session.get('payment_intent'),
                    total_amount=cart.total_amount(),
                    shipping_address_id=address,
                    status='paid',
                )

            order_producers=OrderProducer.objects.filter(payment=payment.id)
            
            if order_producers:
                for order_producer in order_producers:
                    order_producer.order_status="confirmed"
                    order_producer.save()

            # Deduct stock and clear cart
            for item in payment.user.customer_profile.cart.items.all():
                if item.product:
                    item.product.deduct_stock(item.quantity)

            payment.user.customer_profile.cart.items.all().delete()

        except Exception as e:
            print(f"Webhook order processing failed: {e}")
            return HttpResponse(status=500)
    return HttpResponse(status=200)


# =========
# profile
# =========

def order_history(request):
    '''
    Universal order history page
    '''
    orders = OrderPayment.objects.filter(
        user=request.user,
    ).exclude(
        payment_status__in=['pending', 'failed']
    ).order_by('-created_at')
    
    orders_data = []
    
    for order in orders:
        # Build comprehensive order data
        order_info = {
            'order': order,
            'total_amount': order.total_amount,
            'created_at': order.created_at,
            'payment_status': order.payment_status,
            'payment_status_display': order.get_payment_status_display(),
            'shipping_address': order.shipping_address,
            'global_notes': order.global_delivery_notes,
            'producers': []
        }
        
        # Get all producer orders for this payment
        producer_orders = order.producer_orders.select_related(
            'producer'
        ).prefetch_related(
            'order_items__product'
        ).all()
        
        for producer_order in producer_orders:
            producer_data = {
                'producer': producer_order.producer,
                'business_name': producer_order.producer.business_name if producer_order.producer else 'Unknown',
                'status': producer_order.order_status,
                'status_display': producer_order.get_order_status_display(),
                'subtotal': producer_order.producer_subtotal,
                'delivery_date': producer_order.delivered_by,
                'customer_note': producer_order.customer_note,
                'items': []
            }
            
            # Get items for this producer order
            for item in producer_order.order_items.all():
                producer_data['items'].append({
                    'id': item.id,
                    'product_id': item.product.id if item.product else None,
                    'name': item.product_name,
                    'quantity': item.quantity,
                    'price': item.product_price,
                    'line_total': item.line_total,
                    'unit': item.unit
                })
            
            order_info['producers'].append(producer_data)
        
        orders_data.append(order_info)
    
    context = {
        'orders': orders,
        'orders_data': orders_data,
        'total_orders': orders.count(),
        'total_spent': orders.aggregate(total=models.Sum('total_amount'))['total'] or 0,
    }
    
    return render(request, "orders/profile/order_history.html", context)


# =============================================================================
# TC-018 — Recurring Orders (restaurant accounts)
# =============================================================================

@login_required
def recurring_orders_list(request):
    """List all recurring orders for the logged-in restaurant/customer."""
    recurring_orders = RecurringOrder.objects.filter(
        customer=request.user
    ).prefetch_related('items__product', 'instances').order_by('-created_at')

    context = {
        'recurring_orders': recurring_orders,
    }
    return render(request, 'orders/recurring/list.html', context)


@login_required
def recurring_order_detail(request, pk):
    """View and manage a single recurring order."""
    recurring_order = get_object_or_404(RecurringOrder, pk=pk, customer=request.user)
    instances = recurring_order.instances.order_by('-scheduled_date')[:10]

    context = {
        'recurring_order': recurring_order,
        'instances': instances,
    }
    return render(request, 'orders/recurring/detail.html', context)


@login_required
def pause_recurring_order(request, pk):
    """Pause an active recurring order."""
    if request.method != 'POST':
        return redirect('mainApp:orders:recurring_list')
    recurring_order = get_object_or_404(RecurringOrder, pk=pk, customer=request.user)
    if recurring_order.status == 'active':
        recurring_order.status = 'paused'
        recurring_order.save(update_fields=['status'])
    return redirect('mainApp:orders:recurring_list')


@login_required
def resume_recurring_order(request, pk):
    """Resume a paused recurring order."""
    if request.method != 'POST':
        return redirect('mainApp:orders:recurring_list')
    recurring_order = get_object_or_404(RecurringOrder, pk=pk, customer=request.user)
    if recurring_order.status == 'paused':
        recurring_order.status = 'active'
        recurring_order.save(update_fields=['status'])
    return redirect('mainApp:orders:recurring_list')


@login_required
def cancel_recurring_order(request, pk):
    """Cancel a recurring order."""
    if request.method != 'POST':
        return redirect('mainApp:orders:recurring_list')
    recurring_order = get_object_or_404(RecurringOrder, pk=pk, customer=request.user)
    recurring_order.status = 'cancelled'
    recurring_order.save(update_fields=['status'])
    return redirect('mainApp:orders:recurring_list')


@login_required
def edit_instance(request, pk):
    """Edit the next pending instance of a recurring order (quantities only)."""
    instance = get_object_or_404(
        OrderInstance, pk=pk,
        recurring_order__customer=request.user,
        status__in=['pending', 'confirmed']
    )

    if request.method == 'POST':
        with transaction.atomic():
            instance.items.all().delete()
            items_count = int(request.POST.get('items_count', 0))
            for i in range(items_count):
                product_id = request.POST.get(f'product_{i}')
                quantity = request.POST.get(f'quantity_{i}', 1)
                item = instance.recurring_order.items.filter(product_id=product_id).first()
                if item and int(quantity) > 0:
                    OrderInstanceItem.objects.create(
                        instance=instance,
                        product=item.product,
                        product_name=item.product_name,
                        quantity=int(quantity),
                        unit=item.unit,
                    )
            instance.status = 'modified'
            instance.save(update_fields=['status'])
        return redirect('mainApp:orders:recurring_detail', pk=instance.recurring_order_id)

    context = {'instance': instance}
    return render(request, 'orders/recurring/edit_instance.html', context)