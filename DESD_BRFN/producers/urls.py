from django.urls import path
from . import views

urlpatterns = [
    path('producer_login/', views.login_view, name='producer_login'),
    path('producer_register/', views.register_view, name='producer_register'),
]