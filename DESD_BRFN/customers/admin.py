from django.contrib import admin
from .models import (
    Customer,
    CustomerAddress,
    Cart,
    CartItem,
    Order,
    OrderItem,
    PaymentTransaction,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "phone", "postcode")
    search_fields = ("user__username", "user__email", "postcode")


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "line1", "postcode", "is_default")
    list_filter = ("is_default",)
    search_fields = ("line1", "postcode")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "updated_at")


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "cart", "product_name", "quantity", "unit_price")
    search_fields = ("product_name",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "order_number", "customer", "status", "total_amount", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "customer__user__username")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product_name", "quantity", "unit_price", "total_price")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "amount", "status", "transaction_id", "created_at")
    list_filter = ("status",)
    search_fields = ("transaction_id",)
