from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from .forms import CustomerRegistrationForm
from .models import Customer, Cart, CartItem
from mainApp.models import RegularUser
from products.models import Product


def register_customer(request):
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = RegularUser.Role.CUSTOMER
            user.set_password(form.cleaned_data["password"])
            user.save()

            customer = Customer.objects.create(user=user)
            Cart.objects.create(customer=customer)

            login(request, user)
            return redirect("home")
    else:
        form = CustomerRegistrationForm()

    return render(request, "customers/register.html", {"form": form})


@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # Get the customer's cart
    cart = request.user.customer_profile.cart

    # Check if item already exists in cart
    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product_name=product.name,
        unit_price=product.price,
    )

    if not created:
        item.quantity += 1
        item.save()

    return redirect("view_cart")


@login_required
def view_cart(request):
    cart = request.user.customer_profile.cart
    items = cart.items.all()
    total = cart.total_amount()

    return render(request, "customers/cart.html", {
        "cart": cart,
        "items": items,
        "total": total,
    })


@login_required
def remove_from_cart(request, item_id):
    cart = request.user.customer_profile.cart
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()
    return redirect("view_cart")