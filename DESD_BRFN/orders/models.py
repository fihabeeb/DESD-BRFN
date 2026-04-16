# orders/models.py
from django.db import models
from django.conf import settings
from decimal import Decimal
from mainApp.models import RegularUser, Address, CustomerProfile
from products.models import Product
from django.utils import timezone
from datetime import timedelta

class OrderPayment(models.Model):
    """
    For storing Order payment information, address to ship and to which customer
    
    """

    PAYMENT_STATUS_CHOICES = [
        ('pending',    'Pending Payment'),
        ('paid',       'Paid'),
        ('refunded',   'Refunded'),   # full refund only
        ('failed',     'Failed'),
    ]
    
    # Relationships
    # ref customer profile is redundant
    # customer = models.ForeignKey(
    #     CustomerProfile, 
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     related_name='orders'
    # )

    user = models.ForeignKey(
        RegularUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders'
    )
    
    # Stripe/Payment info
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending"
        )

    # Financials
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Shipping info (snapshot from address at time of order)
    shipping_address_id = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL, #idk for this
        null=True,
        related_name='addresses'
    )
    shipping_address = models.TextField(blank=True) # the field below is handled by the system.
    global_delivery_notes = models.TextField(blank=True)

    # TC-017: special delivery instructions for community/bulk orders
    special_instructions = models.TextField(
        blank=True,
        help_text="e.g. 'Delivery to kitchen entrance, contact kitchen manager'"
    )

    # timestamp
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True,blank=True,help_text="when this pending order expires")

    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order #{self.id} - {self.user.email} - £{self.total_amount} - Status: {self.payment_status}"
    
    def save(self, *args, **kwargs):
        if self.shipping_address_id and not self.shipping_address:
            self.shipping_address = self.shipping_address_id.full_address()

        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Check if order has expired"""
        if not self.expires_at or self.payment_status != 'pending':
            return False
        return timezone.now() > self.expires_at
    
    def expire(self):
        """Expire this order if still pending"""
        if self.payment_status == 'pending':
            self.delete()
            return True
        return False
    
    def get_items_by_producer(self):
        """Group items by producer for multi-vendor order display"""
        items_by_producer = {}
        for item in self.items.all():
            producer_id = item.product.producer_id if item.product else None
            if producer_id not in items_by_producer:
                items_by_producer[producer_id] = {
                    'producer': item.product.producer if item.product else None,
                    'items': [],
                    'subtotal': 0
                }
            items_by_producer[producer_id]['items'].append(item)
            items_by_producer[producer_id]['subtotal'] += item.line_total
        return items_by_producer

class OrderProducer(models.Model):
    '''
    Represnets one producer's portion of an order.
    '''

    ORDER_STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready for Pickup/Delivery'),
        ('delivered', 'Delivered'),

        ('cancelled', 'Cancelled'),
    ]
    
    payment = models.ForeignKey(
        OrderPayment,
        on_delete=models.CASCADE,
        related_name='producer_orders'
        )
    
    producer = models.ForeignKey(
        'mainApp.ProducerProfile',
        on_delete=models.PROTECT,
        null=True,
        related_name='producer_orders'
    )

    order_status = models.CharField(max_length=30, choices=ORDER_STATUS_CHOICES, default='pending')

    # financial
    producer_subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    producer_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    delivered_by = models.DateField(null=True, blank=True)

    customer_note = models.TextField(blank=True)

    # TC-017: flag bulk orders from community groups
    is_bulk_order = models.BooleanField(
        default=False,
        help_text="Marked automatically when ordered by a community group account"
    )

    # timestamp
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Calculate commission and payout when first created
        if not self.commission and self.producer_subtotal:
            self.commission = (self.producer_subtotal * Decimal('0.05')).quantize(Decimal('0.01'))

        if not self.producer_payout and self.producer_subtotal: # and self.commission?
            self.producer_payout = self.producer_subtotal - self.commission

        super().save(*args, **kwargs)

    def __str__(self):
        name = self.producer.business_name if self.producer else 'unknown'
        return f"Payment #{self.payment_id} — {name}"


class OrderItem(models.Model):
    """
    Items within an order (snapshot of cart items at purchase time)
    """
    producer_order = models.ForeignKey(
        OrderProducer,
        on_delete=models.CASCADE,
        related_name='order_items',
        null=True,
        )
    
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_items'
        )
    
    # Snapshots (preserve price and details at purchase time)
    product_name = models.CharField(max_length=255)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    unit = models.CharField(max_length=50, blank=True)

    @property
    def line_total(self):
        return self.product_price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"


# =============================================================================
# TC-018 — Recurring Orders (restaurant / business accounts)
# =============================================================================

class RecurringOrder(models.Model):
    """
    Standing order template created by a restaurant / business account.
    A scheduled job creates an OrderInstance from this template each week.
    """

    RECURRENCE_CHOICES = [
        ('weekly', 'Weekly'),
        ('fortnightly', 'Fortnightly'),
    ]

    DAY_CHOICES = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
    ]

    customer = models.ForeignKey(
        RegularUser,
        on_delete=models.CASCADE,
        related_name='recurring_orders'
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default='weekly')
    recurrence_day = models.CharField(max_length=10, choices=DAY_CHOICES, help_text="Day the order is triggered")
    delivery_day = models.CharField(max_length=10, choices=DAY_CHOICES, help_text="Expected delivery day")

    # Delivery address snapshot
    delivery_address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recurring_orders'
    )
    delivery_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    next_scheduled_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Recurring order #{self.id} for {self.customer.username} ({self.recurrence})"


class RecurringOrderItem(models.Model):
    """Items in a recurring order template."""

    recurring_order = models.ForeignKey(
        RecurringOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recurring_items'
    )
    producer = models.ForeignKey(
        'mainApp.ProducerProfile',
        on_delete=models.SET_NULL,
        null=True
    )
    product_name = models.CharField(max_length=255)  # snapshot
    quantity = models.PositiveIntegerField(default=1)
    unit = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"


class OrderInstance(models.Model):
    """
    A single generated instance of a RecurringOrder.
    Starts as a copy of the template items but can be modified per instance.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('confirmed', 'Confirmed'),
        ('modified', 'Modified'),
        ('cancelled', 'Cancelled'),
        ('processed', 'Processed'),
    ]

    recurring_order = models.ForeignKey(
        RecurringOrder,
        on_delete=models.CASCADE,
        related_name='instances'
    )
    scheduled_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Link to the actual OrderPayment once processed through checkout
    order_payment = models.OneToOneField(
        OrderPayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recurring_instance'
    )

    notification_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date']

    def __str__(self):
        return f"Instance #{self.id} of RecurringOrder #{self.recurring_order_id} on {self.scheduled_date}"


class OrderInstanceItem(models.Model):
    """Per-instance item overrides (copied from template, editable per instance)."""

    instance = models.ForeignKey(
        OrderInstance,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name='instance_items'
    )
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"