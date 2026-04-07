from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from customers.forms import CustomerLoginForm


app_name = 'customers'

urlpatterns = [
    path("customer/login", auth_views.LoginView.as_view(
        template_name="customers/login.html",
        authentication_form=CustomerLoginForm,
        redirect_authenticated_user=True,
        extra_context={'title': 'Customer Login'},
        next_page='/',
    ), name='login'),

    path("customer/register/", views.register_customer, name="register"),

    # Cart operations
    path("customer/cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("customer/cart/", views.view_cart, name="view_cart"),
    path("customer/cart/remove/<int:item_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("customer/cart/update/<int:item_id>/", views.update_cart_item, name="update_cart_item"),
    path("customer/profile", views.customer_profile_view, name="profile"),
    path("customer/personal-info", views.customer_personal_info_view, name="personal_info"),
]