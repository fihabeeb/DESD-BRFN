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
            # Set expiry time (30 minutes from now)
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
        # Check if this is a status change from pending to paid
        try:
            old_instance = OrderPayment.objects.get(id=instance.id)
            if old_instance.payment_status == 'pending':
                logger.info(f"OrderPayment #{instance.id} confirmed! Notifying producers...")
                # Here you would send emails/notifications to producers
        except OrderPayment.DoesNotExist:
            pass