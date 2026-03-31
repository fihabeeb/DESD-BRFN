from django.db import models
# from django.conf import settings
from decimal import Decimal
from uuid import uuid4
from mainApp.models import CustomerProfile


def generate_order_number():
    return uuid4().hex[:12].upper()


# # class Customer(models.Model):
# #     user = models.OneToOneField(
# #         settings.AUTH_USER_MODEL,
# #         on_delete=models.CASCADE,
# #         related_name="customer_profile",
# #     )
# #     phone = models.CharField(max_length=20, blank=True)
# #     postcode = models.CharField(max_length=12, blank=True)

# #     def __str__(self):
# #         return self.user.get_full_name() or self.user.username


# # class CustomerAddress(models.Model):
# #     customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="addresses")
# #     line1 = models.CharField(max_length=255)
# #     line2 = models.CharField(max_length=255, blank=True)
# #     city = models.CharField(max_length=100)
# #     postcode = models.CharField(max_length=12)
# #     is_default = models.BooleanField(default=False)

# #     def save(self, *args, **kwargs):
# #         if self.is_default:
# #             CustomerAddress.objects.filter(customer=self.customer, is_default=True).update(is_default=False)
# #         super().save(*args, **kwargs)

# #     def __str__(self):
# #         return f"{self.line1}, {self.postcode}"


class Cart(models.Model):
    customer = models.OneToOneField(CustomerProfile, on_delete=models.CASCADE, related_name="cart")
    updated_at = models.DateTimeField(auto_now=True)

    # @property
    def total_amount(self):
        '''
        Returns total amount fo the cart.
        '''
        # customers only pay the total amount of items (NO COMISSION)
        total = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        return total
    
    def subtotal(self):
        subtotal = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        return round(subtotal,2)
    
    def item_count(self):
        return sum(item.quantity for item in self.items.all())
    
    def get_items_by_producer(self):
        """
        Group cart items by producer.
        Commission is calculated at payout time, not at checkout.
        """
        groups = {}
        for item in self.items.select_related('product__producer').all():
            producer = item.product.producer
            if not producer:
                continue
                
            if producer.id not in groups:
                groups[producer.id] = {
                    'producer': producer,
                    'business_name': producer.business_name,
                    'items': [],
                    'subtotal': Decimal('0.00'),
                    'lead_time_hours': getattr(producer, 'lead_time_hours', 48),
                }
            groups[producer.id]['items'].append(item)
            groups[producer.id]['subtotal'] += item.line_total
        
        return groups
    
    def get_producer_summary(self):
        """
        Get a summary of producers in cart (without full item details)
        Useful for checkout page
        """
        groups = self.get_items_by_producer()
        summary = []
        for producer_id, data in groups.items():
            summary.append({
                'producer_id': producer_id,
                'business_name': data['business_name'],
                'item_count': len(data['items']),
                'total_quantity': sum(item.quantity for item in data['items']),
                'subtotal': data['subtotal'],
                'lead_time_hours': data['lead_time_hours'],
            })
        return summary

    def __str__(self):
        return f"Cart({self.customer})"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="cart_items",
        null=True,
        blank=True
    )  
    product_name= models.CharField(max_length=255, blank=True) #snapshot of the product
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        price = self.unit_price if self.unit_price is not None else Decimal(0.00)
        return price * self.quantity
    
    def save(self, *args, **kwargs):
        "populate snapshots if not available"

        if self.product:
            if not self.product_name:
                self.product_name = self.product.pygame.freetype.name
            if self.unit_price is None:
                self.unit_price = self.product.price
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.quantity} x {self.product_name}"


# class Order(models.Model):
#     customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
#     order_number = models.CharField(max_length=32, unique=True, default=generate_order_number)
#     status = models.CharField(max_length=20, default="pending")
#     total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
#     created_at = models.DateTimeField(auto_now_add=True)

#     def finalize_totals(self):
#         total = sum((item.total_price for item in self.items.all()), Decimal("0.00"))
#         self.total_amount = total
#         self.save(update_fields=["total_amount"])

#     def __str__(self):
#         return f"Order {self.order_number}"


# class OrderItem(models.Model):
#     order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
#     product_name = models.CharField(max_length=255)
#     quantity = models.PositiveIntegerField()
#     unit_price = models.DecimalField(max_digits=10, decimal_places=2)
#     total_price = models.DecimalField(max_digits=12, decimal_places=2)

#     def __str__(self):
#         return f"{self.quantity} x {self.product_name}"


# class PaymentTransaction(models.Model):
#     order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
#     amount = models.DecimalField(max_digits=12, decimal_places=2)
#     status = models.CharField(max_length=32)  # success / failed / pending
#     transaction_id = models.CharField(max_length=128, blank=True, null=True)
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Payment {self.transaction_id or self.pk} ({self.status})"