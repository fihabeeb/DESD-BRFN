from collections import defaultdict
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from customers.forms import CustomerRegistrationForm
from django.contrib import messages
from mainApp.models import Address, CustomerProfile
from mainApp.utils import haversine_miles, BRISTOL_LAT, BRISTOL_LON
from .models import Cart, CartItem
from products.models import Product
from django.contrib.auth import logout
from .forms import CustomerPersonalInfoForm
from django.contrib import messages
from mainApp.decorators import customer_required
import re
import logging

logger = logging.getLogger(__name__)


def register_customer(request):

    if request.user.is_authenticated:
        return redirect('mainApp:home')
    
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # login(request,user)

            messages.success(request, f"Welcome {user.username}! Your customer account has been created successfully.")
            messages.info(request, 'Please log in to continue.')
            return redirect('mainApp:customers:login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomerRegistrationForm()

    context = {
        'form': form,
        'title': 'Customer Registration'
    }
    return render(request, 'customers/register.html', context)

    # if request.method == "POST":
    #     form = CustomerRegistrationForm(request.POST)
    #     if form.is_valid():
    #         user = form.save(commit=False)
    #         user.role = RegularUser.Role.CUSTOMER
    #         user.set_password(form.cleaned_data["password"])
    #         user.save()

    #         customer = Customer.objects.create(user=user)
    #         Cart.objects.create(customer=customer)

    #         login(request, user)
    #         return redirect("home")
    # else:
    #     form = CustomerRegistrationForm()

    # return render(request, "customers/register.html", {"form": form})


@login_required
@require_POST
def add_to_cart(request, product_id):
    """
    Add a product to the logged-in customer's cart.
    Expects POST and optional 'quantity' in POST data.
    """
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get("quantity", 1))
    if quantity < 1:
        quantity = 1

    # Ensure customer profile exists
    customer = getattr(request.user, "customer_profile", None)
    if customer is None:
        customer = CustomerProfile.objects.create(user=request.user)
        Cart.objects.create(customer=customer)

    cart, _ = Cart.objects.get_or_create(customer=customer)

    # Use product FK to find existing cart item
    cart_item = cart.items.filter(product=product).first()
    if cart_item:
        cart_item.quantity += quantity
        cart_item.save()
    else:
        CartItem.objects.create(
            cart=cart,
            product=product,
            product_name=product.name,
            unit_price=product.price,
            quantity=quantity,
        )

    messages.success(request, f"{product.name} added to your cart")

    next_url = request.META.get('HTTP_REFERER', '/')
    return redirect(next_url)

    # return redirect("mainApp:customers:view_cart")


@login_required
def view_cart(request):
    customer = getattr(request.user, "customer_profile", None)
    if not customer:
        return render(request, "customers/cart.html", {"cart": None, "producer_sections": [], "total": Decimal("0.00")})

    cart, _ = Cart.objects.get_or_create(customer=customer)
    items = cart.items.select_related("product__producer").all()

    # TC-013: Group cart items by producer, compute food miles once per producer
    user_lat,user_long = request.user.get_default_address_coordinates()
    grouped = defaultdict(list)
    for item in items:
        producer = item.product.producer if item.product else None
        grouped[producer].append(item)

    producer_sections = []
    for producer, producer_items in grouped.items():
        food_miles = None
        if producer and producer.latitude and producer.longitude:
            # calculate foodmile base on user default address.
            if user_lat and user_long:
                food_miles = round(
                    haversine_miles(producer.latitude, producer.longitude, user_lat, user_long)
                )
            else:
                food_miles = round(
                    haversine_miles(producer.latitude, producer.longitude, BRISTOL_LAT, BRISTOL_LON), 1
                )
        producer_sections.append({
            "producer": producer,
            "items": producer_items,
            "food_miles": food_miles,
        })

    # Sort sections: known producers first, then unknown
    producer_sections.sort(key=lambda s: s["producer"].business_name if s["producer"] else "")

    total = cart.total_amount()
    return render(request, "customers/cart.html", {
        "cart": cart,
        "producer_sections": producer_sections,
        "total": total,
    })


@login_required
@require_POST
def remove_from_cart(request, item_id):
    """
    Remove a cart item. POST only.
    """
    customer = getattr(request.user, "customer_profile", None)
    if not customer:
        return redirect("mainApp:customers:view_cart")

    cart = getattr(customer, "cart", None)
    if not cart:
        return redirect("mainApp:customers:view_cart")

    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()
    return redirect("mainApp:customers:view_cart")



@login_required
@require_POST
def update_cart_item(request, item_id):
    """
    Update the quantity of a cart item.
    """
    customer = getattr(request.user, "customer_profile", None)
    if not customer:
        messages.error(request, "No customer profile found.")
        return redirect("mainApp:customers:view_cart")

    cart = getattr(customer, "cart", None)
    if not cart:
        messages.error(request, "No cart found.")
        return redirect("mainApp:customers:view_cart")

    item = get_object_or_404(CartItem, id=item_id, cart=cart)

    try:
        new_quantity = int(request.POST.get("quantity", 1))
    except ValueError:
        messages.error(request, "Invalid quantity.")
        return redirect("mainApp:customers:view_cart")

    if new_quantity < 1:
        messages.warning(request, "Quantity must be at least 1.")
        new_quantity = 1

    # Optional: enforce stock limit
    if item.product and new_quantity > item.product.stock_quantity:
        messages.error(request, f"Only {item.product.stock_quantity} units available.")
        new_quantity = item.product.stock_quantity

    item.quantity = new_quantity
    item.save()

    messages.success(request, f"Updated quantity for {item.product_name}.")
    return redirect("mainApp:customers:view_cart")


@login_required
def customer_profile_view(request):
    """
    Customer dashboard: future order history + button to view personal info.
    """
    return render(request, "customers/profile_page.html", {})


@login_required
@customer_required
def customer_personal_info_view(request):
    """Customer personal information management"""
    user = request.user

    # DELETE ACCOUNT HANDLER
    if request.method == "POST" and "delete_account" in request.POST:
        user.delete()
        logout(request)
        messages.success(request, "Your account has been deleted successfully. We're sorry to see you go!")
        return redirect("mainApp:home")
    
    # GET OR CREATE CUSTOMER PROFILE
    try:
        profile = CustomerProfile.objects.get(user=user)
    except CustomerProfile.DoesNotExist:
        logger.info(f"Creating missing profile for user {user.username}")
        profile = CustomerProfile.objects.create(user=user)
        messages.info(request, "Customer profile was created.")
    
    # GET ADDRESSES
    all_addresses = user.addresses.all()
    default_address = all_addresses.filter(is_default=True).first()
    other_addresses = all_addresses.exclude(id=default_address.id) if default_address else all_addresses
    
    # PROCESS FORM
    if request.method == "POST":
        form = CustomerPersonalInfoForm(request.POST, user=user)
        
        if form.is_valid():
            try:
                user = form.save()
                
                # Handle session after password change
                if form.cleaned_data.get('password1'):
                    update_session_auth_hash(request, user)
                    messages.success(request, "Password updated successfully!")
                
                messages.success(request, "Your information has been updated successfully!")
                return redirect("mainApp:customers:personal_info")
                
            except Exception as e:
                logger.error(f"Error updating customer info: {e}", exc_info=True)
                messages.error(request, "An error occurred while updating your information. Please try again.")
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    if field == '__all__':
                        messages.error(request, error)
                    else:
                        field_label = field.replace('_', ' ').title()
                        messages.error(request, f"{field_label}: {error}")
    
    else:
        # GET request - populate initial data for form
        initial_data = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": user.phone_number,
        }
        
        form = CustomerPersonalInfoForm(user=user, initial=initial_data)
    
    context = {
        'form': form,
        'user': user,
        'profile': profile,
        'all_addresses': all_addresses,
        'default_address': default_address,
        'other_addresses': other_addresses,
    }
    
    return render(request, "customers/personal_info.html", context)