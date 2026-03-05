from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, logout
from mainApp.models import RegularUser

def home(request):
    return render(request, 'mainApp/home.html')


def logout_view(request):
    logout(request)
    return redirect('home')


def profile_redirect(request):
    user = request.user

    if user.role == RegularUser.Role.PRODUCER:
            return redirect('producer_myproduct')  #TODO: maybe profiles to be implemented
    elif user.role == RegularUser.Role.CUSTOMER:
        return redirect('customer_profile')  # Customer sees their profile/order history
    elif user.role == RegularUser.Role.COMMUNITY_MEMBER:
        return redirect('community_profile')
    elif user.role == RegularUser.Role.SYSTEM_ADMIN:
        return redirect('admin:index')
    else:
    # messages.warning(request, 'Please complete your profile setup.')
        return redirect('home')