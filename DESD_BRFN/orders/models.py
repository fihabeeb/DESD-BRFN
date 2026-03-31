# orders/models.py
from django.db import models
from django.conf import settings
from decimal import Decimal
from mainApp.models import RegularUser, Address, CustomerProfile
from products.models import Product

class Order(models.Model):
    """Order model to store completed purchases"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('processing', 'Processing'),
        ('confirmed', 'Confirmed'),
        ('ready', 'Ready for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    
    # Relationships
    customer = models.ForeignKey(
        CustomerProfile, 
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders'
    )
    user = models.ForeignKey(
        RegularUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders'
    )
    
    # Stripe/Payment info
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Order details
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Financials
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Shipping info (snapshot from address at time of order)
    # shipping_address = models.TextField(blank=True)
    # shipping_address_id = models.IntegerField(null=True, blank=True)  # Reference to Address
    shipping_address_id = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        null=True,
        related_name='addresses'
    )

    # Delivery info
    delivery_date = models.DateField(null=True, blank=True)
    delivery_notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Order #{self.id} - {self.user.email}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
    
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

class OrderItem(models.Model):
    """Items within an order (snapshot of cart items at purchase time)"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Product, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='order_items'
    )
    producer = models.ForeignKey(
        'mainApp.ProducerProfile',
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