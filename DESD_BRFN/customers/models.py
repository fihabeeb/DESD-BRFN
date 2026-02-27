from django.db import models
from django.conf import settings
from decimal import Decimal
from uuid import uuid4


def generate_order_number():
    return uuid4().hex[:12].upper()


class Customer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )
    phone = models.CharField(max_length=20, blank=True)
    postcode = models.CharField(max_length=12, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class CustomerAddress(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
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
        if self.is_default:
            CustomerAddress.objects.filter(customer=self.customer, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.line1}, {self.postcode}"


class Cart(models.Model):
    customer = models.OneToOneField(Customer, on_delete=models.CASCADE, related_name="cart")
    updated_at = models.DateTimeField(auto_now=True)

    def total_amount(self):
        return sum((item.line_total for item in self.items.all()), Decimal("0.00"))

    def __str__(self):
        return f"Cart({self.customer})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product_name = models.CharField(max_length=255)  # simple placeholder
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return (self.unit_price or Decimal("0.00")) * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    order_number = models.CharField(max_length=32, unique=True, default=generate_order_number)
    status = models.CharField(max_length=20, default="pending")
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)

    def finalize_totals(self):
        total = sum((item.total_price for item in self.items.all()), Decimal("0.00"))
        self.total_amount = total
        self.save(update_fields=["total_amount"])

    def __str__(self):
<<<<<<< HEAD
        return f"Order {self.order_number}"
=======
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
            models.CheckConstraint(condition=models.Q(subtotal__gte=0), name="suborder_subtotal_non_negative"),
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
>>>>>>> bacda0d (Turned off customers app)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)

<<<<<<< HEAD
=======
    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="orderitem_quantity_positive"),
            models.CheckConstraint(condition=models.Q(total_price__gte=0), name="orderitem_total_non_negative"),
        ]
        indexes = [models.Index(fields=["product", "suborder"])]

>>>>>>> bacda0d (Turned off customers app)
    def __str__(self):
        return f"{self.quantity} x {self.product_name}"


class PaymentTransaction(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=32)  # success / failed / pending
    transaction_id = models.CharField(max_length=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.transaction_id or self.pk} ({self.status})"