# orders/signals.py
import logging
from datetime import timedelta
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction

from orders.models import OrderPayment, OrderProducer, OrderItem
from customers.models import CartItem
from products.models import Product
from mainApp.utils import haversine_miles

logger = logging.getLogger(__name__)


@receiver(post_save, sender=OrderPayment)
def handle_order_payment_created(sender, instance, created, **kwargs):
    """
    Handle new OrderPayment creation:
    - Set expiry time for pending orders
    - Schedule cleanup if needed
    - Log creation
    """
    if created:
        logger.info(f"OrderPayment #{instance.id} created with status: {instance.payment_status}")
        
        if instance.payment_status == 'pending':
            # Set expiry time (15 minutes from now)
            expiry_time = timezone.now() + timedelta(minutes=15)
            instance.expires_at = expiry_time
            instance.save(update_fields=['expires_at'])
            
            logger.info(f"OrderPayment #{instance.id} will expire at {expiry_time}")

@receiver(post_save, sender=OrderProducer)
def handle_producer_order_created(sender, instance, created, **kwargs):
    """
    Handle new OrderProducer creation
    """
    if created:
        if instance.payment.shipping_address_id:
            producer_lat, producer_long = instance.producer.user.get_default_address_coordinates()
            user_lat, user_long = instance.payment.shipping_address_id.get_coordinates()

            distance = haversine_miles(producer_lat, producer_long, user_lat, user_long)

            instance.food_mile_distance = distance

            logger.info(f"OrderProducer #{instance.id} created for OrderPayment #{instance.payment.id}")


@receiver(post_save, sender=OrderItem)
def handle_order_item_created(sender, instance, created, **kwargs):
    """
    Handle new OrderItem creation
    """
    if created:
        logger.info(f"OrderItem created: {instance.quantity} x {instance.product_name}")


@receiver(post_save, sender=OrderPayment)
def notify_producers_on_confirmation(sender, instance, created, **kwargs):
    """
    When an order is confirmed (paid), notify producers
    """
    if not created and instance.payment_status == 'paid':
        try:
            old_instance = OrderPayment.objects.get(id=instance.id)
            if old_instance.payment_status == 'pending':
                logger.info(f"OrderPayment #{instance.id} confirmed! Notifying producers...")
        except OrderPayment.DoesNotExist:
            pass


@receiver(post_save, sender=OrderPayment)
def log_purchased_interactions(sender, instance, created, **kwargs):
    """Record a UserInteraction(purchased) for every item in a newly paid order."""
    if instance.payment_status != 'paid':
        return

    try:
        from interactions.models import UserInteraction
        items = instance.producer_orders.prefetch_related('order_items__product').all()
        bulk = []
        for producer_order in items:
            for item in producer_order.order_items.all():
                if item.product:
                    bulk.append(UserInteraction(
                        user=instance.user,
                        interaction_type=UserInteraction.PURCHASED,
                        product=item.product,
                        metadata={"order_payment_id": instance.id, "quantity": item.quantity},
                    ))
        if bulk:
            UserInteraction.objects.bulk_create(bulk, ignore_conflicts=True)
    except Exception as e:
        logger.warning("Failed to log purchased interactions for order %s: %s", instance.id, e)