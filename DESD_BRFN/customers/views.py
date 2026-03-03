from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import CustomerRegistrationForm
from .models import Customer, Cart
from mainApp.models import RegularUser

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