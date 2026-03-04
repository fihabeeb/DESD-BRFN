from django.urls import path
from . import views

urlpatterns = [
    path('producer/login', views.login_view, name='producer_login'),
    path('producer/register', views.register_view, name='producer_register'),
    path('producer/products', views.myproduct_view, name="producer_myproduct"),
    # producer_product_add
    path('producer/products/add', views.addproduct_view, name="producer_product_add"),
    path('producer/products/<int:product_id>/edit/', views.product_edit_view, name='producer_product_edit'),
]