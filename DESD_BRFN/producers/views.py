from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth import get_user_model
from mainApp.models import ProducerProfile
from django.contrib.auth import authenticate, login
# Create your views here.

User = get_user_model()

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('home')
        else:
            return render(request, 'producer_login.html', {'error': 'Invalid credentials'})
    return render(request, 'producer_login.html')


def register_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password1 = request.POST['password1']
        password2 = request.POST['password2']
        if password1 != password2:
            return render(request, 'producer_register.html', {'error': 'Passwords do not match'})
        if User.objects.filter(email=email).exists():
            return render(request, 'producer_register.html', {'error': 'Username already taken'})
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.role = 'producer'
        user.save()
        ProducerProfile.objects.create(user=user)
        return redirect('producer_login')
    return render(request, 'producer_register.html')
