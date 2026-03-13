from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, logout
from mainApp.models import RegularUser

def home(request):
    return redirect('mainApp:products:product_list')


def logout_view(request):
    logout(request)
    return redirect('mainApp:home')


def profile_redirect(request):
    user = request.user

    if user.role == RegularUser.Role.PRODUCER:
        return redirect('mainApp:producers:myproduct')  #TODO: maybe profiles to be implemented
    elif user.role == RegularUser.Role.CUSTOMER:
        return redirect('mainApp:customers:profile')  # Customer sees their profile/order history
    elif user.role == RegularUser.Role.COMMUNITY_MEMBER:
        return redirect('mainApp:customers:profile')
    elif user.role == RegularUser.Role.SYSTEM_ADMIN:
        return redirect('admin:index')
    else:
    # messages.warning(request, 'Please complete your profile setup.')
        return redirect('home')