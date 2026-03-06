from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    path("customer-register/", views.register_customer, name="register_customer"),

    # Cart operations
    path("customer/cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("customer/cart/", views.view_cart, name="view_cart"),
    path("customer/cart/remove/<int:item_id>/", views.remove_from_cart, name="remove_from_cart"),
]