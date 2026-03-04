from django.urls import path
from . import views

urlpatterns = [
    path("register/", views.register_customer, name="register_customer"),
]