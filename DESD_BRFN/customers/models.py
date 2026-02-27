"""
Includes: Customer, CustomerAddress, Cart, CartItem, Order, OrderSub,
OrderItem, PaymentTransaction, Review, RecurringOrderTemplate, FoodMilesRecord.
"""
from django.db import models
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


ACCOUNT_TYPE_CHOICES = [
    ("individual", "Individual"),
    ("community", "Community Group"),
    ("restaurant", "Restaurant"),
    ("producer", "Producer"),
]

ORDER_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("paid", "Paid"),
    ("processing", "Processing"),
    ("delivered", "Delivered"),
    ("cancelled", "Cancelled"),
]

GATEWAY_CHOICES = [
    ("stripe", "Stripe"),
    ("paypal", "PayPal"),
    ("manual", "Manual"),
]


def generate_order_number():
    """Generate a short unique order number."""
    return uuid4().hex[:12].upper()


class Customer(models.Model):
    """
    Customer profile linked to Django user.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    phone = models.CharField(max_length=20, blank=True)
    account_type = models.CharField(
        max_length=20, choices=ACCOUNT_TYPE_CHOICES, default="individual"
    )
    postcode = models.CharField(max_length=12, blank=True)

    class Meta:
        indexes = [models.Index(fields=["account_type"]), models.Index(fields=["postcode"])]

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    def default_address(self):
        """Return the default delivery address or None."""
        return self.addresses.filter(is_default=True).first()


class CustomerAddress(models.Model):
    """
    Delivery addresses for customers.
    """
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="addresses"
    )
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=12)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["postcode"]), models.Index(fields=["customer"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(postcode__gt=""), name="customeraddress_postcode_non_empty"
            )
        ]

    def save(self, *args, **kwargs):
        """
        Ensure only one default address per customer.
        """
        if self.is_default:
            CustomerAddress.objects.filter(customer=self.customer, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.line1}, {self.postcode}"


class Cart(models.Model):
    """
    Active shopping cart for a customer (one cart per customer).
    """
    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="cart"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def total_amount(self):
        """Sum of line totals for all items in the cart."""
        return sum((item.line_total for item in self.items.all()), Decimal("0.00"))

    def grouped_by_producer(self):
        """
        Return a dict mapping producer -> list of CartItem.
        Assumes Product model has `producer` FK.
        """
        grouped = {}
        for item in self.items.select_related("product__producer"):
            producer = getattr(item.product, "producer", None)
            grouped.setdefault(producer, []).append(item)
        return grouped

    def __str__(self):
        return f"Cart({self.customer})"


class CartItem(models.Model):
    """
    Item in a shopping cart. Unit price is snapshotted at add time.
    """
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product", on_delete=models.PROTECT, related_name="cart_items"
    )
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        indexes = [models.Index(fields=["cart", "product"])]

    @property
    def line_total(self):
        return (self.unit_price or Decimal("0.00")) * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product} in {self.cart}"


class Order(models.Model):
    """
    Top-level customer order. May contain multiple OrderSub entries (per producer).
    """
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    order_number = models.CharField(max_length=32, unique=True, default=generate_order_number)
    status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default="pending")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    delivery_address_snapshot = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["customer", "status", "created_at"])]

    def calculate_commission(self, rate=Decimal("0.05")):
        """Calculate and set commission amount based on total_amount."""
        self.commission_amount = (self.total_amount * rate).quantize(Decimal("0.01"))
        return self.commission_amount

    def finalize_totals(self):
        """Recompute totals from suborders and persist."""
        total = sum((sub.subtotal for sub in self.suborders.all()), Decimal("0.00"))
        self.total_amount = total
        self.calculate_commission()
        self.save(update_fields=["total_amount", "commission_amount"])

    def split_multi_vendor_order(self):
        """
        Create OrderSub and OrderItem entries grouped by product.producer.
        This method assumes the customer's cart items are the source of truth.
        """
        from products.models import Product  # linking to product app (alif)
        from producers.models import Producer  # linking to producer app (fadil)

        cart = getattr(self.customer, "cart", None)
        if not cart:
            return

        grouped = cart.grouped_by_producer()
        with transaction.atomic():
            # Remove existing suborders if re-splitting
            self.suborders.all().delete()
            for producer, items in grouped.items():
                sub = OrderSub.objects.create(order=self, producer=producer, subtotal=Decimal("0.00"))
                subtotal = Decimal("0.00")
                for ci in items:
                    oi = OrderItem.objects.create(
                        suborder=sub,
                        product=ci.product,
                        quantity=ci.quantity,
                        unit_price=ci.unit_price,
                        total_price=(ci.unit_price * ci.quantity),
                    )
                    subtotal += oi.total_price
                sub.subtotal = subtotal
                sub.payout_amount = (subtotal * Decimal("0.95")).quantize(Decimal("0.01"))
                sub.save()
            self.finalize_totals()

    def mark_paid(self, transaction: "PaymentTransaction"):
        """Mark order as paid when a successful transaction is recorded."""
        if transaction and transaction.status == "success":
            self.status = "paid"
            self.save(update_fields=["status"])

    def __str__(self):
        return f"Order {self.order_number} ({self.customer})"


class OrderSub(models.Model):
    """
    Per-producer sub-order linked to a top-level Order.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="suborders")
    producer = models.ForeignKey(
        "producers.Producer", on_delete=models.PROTECT, related_name="suborders"
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payout_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    delivery_date = models.DateField(null=True, blank=True)
    lead_time_hours = models.PositiveIntegerField(default=48)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0),
                name="suborder_subtotal_non_negative"),
        ]
        indexes = [models.Index(fields=["producer", "delivery_date"])]

    def is_within_lead_time(self, delivery_date):
        """Return True if delivery_date respects producer lead time."""
        if not delivery_date:
            return False
        min_date = (timezone.now() + timezone.timedelta(hours=self.lead_time_hours)).date()
        return delivery_date >= min_date

    def __str__(self):
        return f"SubOrder {self.id} for {self.producer}"


class OrderItem(models.Model):
    """
    Item in a per-producer sub-order.
    """
    suborder = models.ForeignKey(OrderSub, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="orderitem_quantity_positive"),
            models.CheckConstraint(condition=models.Q(total_price__gte=0), name="orderitem_total_non_negative"),
        ]
        indexes = [models.Index(fields=["product", "suborder"])]

    def __str__(self):
        return f"{self.quantity} x {self.product} (OrderSub {self.suborder.id})"


class PaymentTransaction(models.Model):
    """
    Record of payment gateway transactions.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    gateway = models.CharField(max_length=32, choices=GATEWAY_CHOICES, default="stripe")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=32)  # e.g., success, failed, pending
    transaction_id = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    raw_response = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.transaction_id or self.pk} ({self.status})"


class Review(models.Model):
    """
    Product review linked to a delivered order.
    Enforces one review per product per customer.
    """
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="reviews")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="reviews")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    title = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    moderated = models.BooleanField(default=False)

    class Meta:
        unique_together = ("product", "customer")
        indexes = [models.Index(fields=["product", "customer"])]

    def __str__(self):
        return f"Review {self.rating} for {self.product} by {self.customer}"


class RecurringOrderTemplate(models.Model):
    """
    Template for recurring orders (business customers).
    Template stores a JSON snapshot of items and quantities or can be expanded to M2M.
    """
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="recurring_templates")
    name = models.CharField(max_length=128)
    frequency = models.CharField(max_length=32, choices=[("weekly", "Weekly"), ("fortnightly", "Fortnightly")])
    next_run = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    template_items = models.JSONField(help_text="[{product_id: int, quantity: int}, ...]")

    class Meta:
        indexes = [models.Index(fields=["customer", "is_active"])]

    def __str__(self):
        return f"RecurringTemplate {self.name} ({self.customer})"


class FoodMilesRecord(models.Model):
    """
    Cached food miles calculation between a product's producer location and a customer address.
    """
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE, related_name="food_miles")
    customer_address = models.ForeignKey(CustomerAddress, on_delete=models.CASCADE, related_name="food_miles")
    distance_miles = models.DecimalField(max_digits=8, decimal_places=2)
    calculated_at = models.DateTimeField(auto_now=True)
    method = models.CharField(max_length=32, default="geodesic")  # 'geodesic' or 'road'

    class Meta:
        unique_together = ("product", "customer_address")
        indexes = [models.Index(fields=["product", "customer_address"])]

    def __str__(self):
        return f"{self.distance_miles} miles for {self.product} -> {self.customer_address}"

    @staticmethod
    def calculate_distance(lat1, lon1, lat2, lon2, method="geodesic"):
        """
        Calculate distance in miles between two lat/lon pairs.
        Uses geopy if available; otherwise returns None.
        """
        try:
            from geopy.distance import geodesic, great_circle
        except Exception:
            return None

        if method == "road":
            # Road distance requires external routing service; fallback to geodesic
            return Decimal(str(geodesic((lat1, lon1), (lat2, lon2)).miles)).quantize(Decimal("0.01"))
        return Decimal(str(geodesic((lat1, lon1), (lat2, lon2)).miles)).quantize(Decimal("0.01"))