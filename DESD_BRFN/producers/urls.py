from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import ProducerLoginForm

app_name = "producers"

urlpatterns = [
    # path('producer/login', views.login_view, name='producer_login'),

    # basic
    path('producer/login', auth_views.LoginView.as_view(
        template_name='producers/login.html',
        authentication_form=ProducerLoginForm,
        redirect_authenticated_user=True,
        extra_context={'title': 'Producer Login'},
        next_page='/'
    ), name='login'),
    path('producer/register', views.register_view, name='register'),

    # producer profile page
    path('producer/products', views.myproduct_view, name="myproduct"),
    path('producer/products/add', views.addproduct_view, name="add_product"),
    path('producer/products/<int:product_id>/edit/', views.product_edit_view, name='edit_product'),
    path('product/<int:product_id>/delete/', views.delete_product, name='delete_product'),
    path("producer/personal-info", views.personal_info_view, name="personal_info"),
]