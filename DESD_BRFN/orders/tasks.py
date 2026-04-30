from celery import shared_task
from django.utils import timezone
from orders.models import OrderPayment
import logging

logger = logging.getLogger(__name__)


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


# =============================================================================
# TC-018 — Generate recurring order instances
# =============================================================================

@shared_task
def generate_recurring_order_instances():
    """
    Daily job: create OrderInstance records for active RecurringOrders whose
    next_scheduled_date is today or within the next 2 days (lead-time window).
    Sends a notification email to the restaurant.
    """
    from datetime import date, timedelta
    from orders.models import RecurringOrder, OrderInstance, OrderInstanceItem

    today = date.today()
    lead_window = today + timedelta(days=2)

    active_orders = RecurringOrder.objects.filter(
        status='active',
        next_scheduled_date__lte=lead_window,
    ).select_related('customer').prefetch_related('items__product')

    created = 0
    for ro in active_orders:
        # Avoid duplicate instances for the same scheduled date
        if OrderInstance.objects.filter(
            recurring_order=ro,
            scheduled_date=ro.next_scheduled_date
        ).exists():
            continue

        instance = OrderInstance.objects.create(
            recurring_order=ro,
            scheduled_date=ro.next_scheduled_date,
            status='pending',
        )

        # Copy template items to instance
        for template_item in ro.items.all():
            OrderInstanceItem.objects.create(
                instance=instance,
                product=template_item.product,
                product_name=template_item.product_name,
                quantity=template_item.quantity,
                unit=template_item.unit,
            )

        # Advance next_scheduled_date
        if ro.recurrence == 'weekly':
            ro.next_scheduled_date += timedelta(weeks=1)
        else:  # fortnightly
            ro.next_scheduled_date += timedelta(weeks=2)
        ro.save(update_fields=['next_scheduled_date'])

        # Send notification (using Django's email backend once configured)
        _send_recurring_notification(ro, instance)
        created += 1

    return f"Created {created} recurring order instances"


def _send_recurring_notification(recurring_order, instance):
    """Send an email notification to the restaurant about their upcoming order."""
    from django.core.mail import send_mail
    from django.conf import settings

    user = recurring_order.customer
    if not user.email:
        return

    days_until = (instance.scheduled_date - timezone.now().date()).days

    try:
        send_mail(
            subject=f"Your weekly order is being prepared — {days_until} days to review",
            message=(
                f"Hi {user.get_full_name() or user.username},\n\n"
                f"Your recurring order (#{recurring_order.id}) is scheduled for "
                f"{instance.scheduled_date.strftime('%A, %d %B %Y')}.\n\n"
                f"You have {days_until} day(s) to review or modify this order.\n\n"
                f"Log in at Bristol Regional Food Network to make any changes.\n\n"
                f"Thank you,\nThe Bristol Regional Food Network Team"
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@farmdirect.com'),
            recipient_list=[user.email],
            fail_silently=True,
        )
        instance.notification_sent = True
        instance.save(update_fields=['notification_sent'])
    except Exception as e:
        logger.warning(f"Failed to send recurring order notification: {e}")


# =============================================================================
# TC-019 — Expire surplus deals
# =============================================================================

@shared_task
def expire_surplus_deals():
    """
    Scheduled job: mark SurplusDeals as inactive when expires_at has passed.
    """
    from products.models import SurplusDeal

    now = timezone.now()
    expired = SurplusDeal.objects.filter(is_active=True, expires_at__lte=now)
    count = expired.count()
    expired.update(is_active=False)
    return f"Expired {count} surplus deals"