from celery import shared_task
from django.utils import timezone
from orders.models import OrderPayment

@shared_task
def cleanup_expired_orders():
    now = timezone.now()

    expired_orders = OrderPayment.objects.filter(
        payment_status='pending',
        expires_at__lt=now
    )

    count = expired_orders.count()
    expired_orders.delete()

    return f"Deleted {count} expired orders"