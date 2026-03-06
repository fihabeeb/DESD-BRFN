from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import ProducerLoginForm

app_name = "producers"

urlpatterns = [
    # path('producer/login', views.login_view, name='producer_login'),

    # Login using Django's built-in LoginView with custom form
    path('producer/login', auth_views.LoginView.as_view(
        template_name='producer_login.html',
        authentication_form=ProducerLoginForm,
        redirect_authenticated_user=True,
        extra_context={'title': 'Producer Login'},
        next_page='/'
    ), name='producer_login'),

    path('producer/register', views.register_view, name='producer_register'),
    path('producer/register', views.register_view, name='register'),

    path('producer/products', views.myproduct_view, name="myproduct"),
    # producer_product_add
    path('producer/products/add', views.addproduct_view, name="add_product"),
    path('producer/products/<int:product_id>/edit/', views.product_edit_view, name='edit_product'),
]