from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, logout
from mainApp.models import RegularUser, Address
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


User = get_user_model()

def home(request):
    return redirect('mainApp:products:product_list')


def logout_view(request):
    logout(request)
    return redirect('mainApp:home')


def profile_redirect(request):
    user = request.user

    if user.role == RegularUser.Role.PRODUCER:
        return redirect('mainApp:producers:profile')  #TODO: maybe profiles to be implemented
    elif user.role == RegularUser.Role.CUSTOMER:
        return redirect('mainApp:customers:profile')  # Customer sees their profile/order history
    elif user.role == RegularUser.Role.COMMUNITY_MEMBER:
        return redirect('mainApp:customers:profile')
    elif user.role == RegularUser.Role.RESTAURANT:
        return redirect('mainApp:customers:profile')
    elif user.role == RegularUser.Role.SYSTEM_ADMIN:
        return redirect('admin:index')
    else:
        return redirect('mainApp:home')
    

# --------
# address
# --------
from mainApp.forms import AddressForm



@login_required
def manage_addresses(request):
    """Main address management page"""
    addresses = request.user.addresses.all().order_by('-is_default', '-created_at')
    
    # Create separate lists for each address type (matches what template expects)
    context = {
        'addresses': addresses,
        'home_addresses': addresses.filter(address_type='home'),
        'shipping_addresses': addresses.filter(address_type='shipping'),
        'billing_addresses': addresses.filter(address_type='billing'),
        'business_addresses': addresses.filter(address_type='business'),
        'farm_addresses': addresses.filter(address_type='farm'),
        'address_types': Address.ADDRESS_TYPES,
    }
    
    return render(request, 'addresses/manage_addresses.html', context)


@login_required
def add_address(request):
    """Add a new address"""
    if request.method == 'POST':
        form = AddressForm(request.POST, user = request.user)
        if form.is_valid():
            address = form.save(commit=False)
            address.save()
            
            messages.success(request, f'Address "{address.label or address.address_type}" added successfully!')
            return redirect('mainApp:manage_addresses')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = AddressForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Add New Address',
    }
    return render(request, 'addresses/address_form.html', context)


@login_required
def edit_address(request, address_id):
    """Edit an existing address"""
    address = get_object_or_404(Address, id=address_id, user=request.user)
    
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address, user=request.user)
        if form.is_valid():
            form.save(commit=False)
            address.save()
            
            messages.success(request, f'Address "{address.label or address.address_type}" updated successfully!')
            return redirect('mainApp:manage_addresses')
        # else:
        #     for field, errors in form.errors.items():
        #         for error in errors:
        #             messages.error(request, f'{field}: {error}')
    else:
        form = AddressForm(instance=address, user=request.user)
    
    context = {
        'form': form,
        'address': address,
        'title': 'Edit Address',
    }
    return render(request, 'addresses/address_form.html', context)

@login_required
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)

    if request.method == 'POST':
        address_label = address.label or f"{address.get_address_type_display()} Address"
        if address.address_type == "farm":
            messages.error(request, f"Cannot delete farm type address")
            return redirect('mainApp:manage_addresses')
        try:
            address.delete()
            messages.success(request, f'Address "{address_label}" deleted successfully!')
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect('mainApp:manage_addresses')


@login_required
def set_default_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)
    

    if request.method == 'POST':
        if address.is_default:
            messages.info(request, 'This address is already your default.')
            return redirect('mainApp:manage_addresses')

        if request.user.role == "producer" and address.address_type!="farm":
            messages.error(request, 'Could not set as default. Producers must use a farm address as default.')
            return redirect('mainApp:manage_addresses')
        try:
            Address.objects.filter(
                    user=request.user,
                    is_default=True
                ).update(is_default=False)
            address.is_default = True
            address.save()
            address.refresh_from_db()

            if address.is_default:
                messages.success(request, f'{address.get_address_type_display()} address set as default!')
            else:
                messages.error(request, 'Could not set as default. Producers must use a farm address as default.')
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect('mainApp:manage_addresses')
