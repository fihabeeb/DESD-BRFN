# from django.contrib import admin
# from .models import (
#     Customer, CustomerAddress, Cart, CartItem,
#     Order, OrderSub, OrderItem,
#     PaymentTransaction, Review,
#     RecurringOrderTemplate, FoodMilesRecord
# )


# @admin.register(Customer)
# class CustomerAdmin(admin.ModelAdmin):
#     list_display = ("user", "account_type", "phone", "postcode")
#     list_filter = ("account_type",)
#     search_fields = ("user__username", "user__email", "postcode")


# @admin.register(CustomerAddress)
# class CustomerAddressAdmin(admin.ModelAdmin):
#     list_display = ("customer", "line1", "city", "postcode", "is_default")
#     list_filter = ("is_default", "city")
#     search_fields = ("customer__user__email", "postcode")


# class CartItemInline(admin.TabularInline):
#     model = CartItem
#     extra = 0


# @admin.register(Cart)
# class CartAdmin(admin.ModelAdmin):
#     list_display = ("customer", "updated_at")
#     inlines = [CartItemInline]


# class OrderItemInline(admin.TabularInline):
#     model = OrderItem
#     extra = 0


# class OrderSubInline(admin.TabularInline):
#     model = OrderSub
#     extra = 0


# @admin.register(Order)
# class OrderAdmin(admin.ModelAdmin):
#     list_display = ("order_number", "customer", "status", "total_amount", "created_at")
#     list_filter = ("status", "created_at")
#     search_fields = ("order_number", "customer__user__email")
#     inlines = [OrderSubInline]


# @admin.register(OrderSub)
# class OrderSubAdmin(admin.ModelAdmin):
#     list_display = ("order", "producer", "subtotal", "payout_amount", "delivery_date")
#     list_filter = ("delivery_date", "producer")


# @admin.register(OrderItem)
# class OrderItemAdmin(admin.ModelAdmin):
#     list_display = ("suborder", "product", "quantity", "total_price")
#     list_filter = ("product",)


# @admin.register(PaymentTransaction)
# class PaymentTransactionAdmin(admin.ModelAdmin):
#     list_display = ("order", "gateway", "amount", "status", "transaction_id", "created_at")
#     list_filter = ("gateway", "status")
#     search_fields = ("transaction_id",)


# @admin.register(Review)
# class ReviewAdmin(admin.ModelAdmin):
#     list_display = ("product", "customer", "rating", "created_at", "moderated")
#     list_filter = ("rating", "moderated")
#     search_fields = ("product__name", "customer__user__email")


# @admin.register(RecurringOrderTemplate)
# class RecurringOrderTemplateAdmin(admin.ModelAdmin):
#     list_display = ("customer", "name", "frequency", "next_run", "is_active")
#     list_filter = ("frequency", "is_active")


# @admin.register(FoodMilesRecord)
# class FoodMilesRecordAdmin(admin.ModelAdmin):
#     list_display = ("product", "customer_address", "distance_miles", "method", "calculated_at")
#     list_filter = ("method",)

