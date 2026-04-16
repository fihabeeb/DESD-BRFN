from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import ProducerLoginForm, RestaurantLoginForm

app_name = "producers"

urlpatterns = [
    # basic
    path('producer/login/', auth_views.LoginView.as_view(
        template_name='producers/login.html',
        authentication_form=ProducerLoginForm,
        redirect_authenticated_user=True,
        extra_context={'title': 'Producer Login'},
        next_page='/'
    ), name='login'),
    path('producer/register/', views.register_view, name='register'),

    # TC-018: Restaurant registration & login
    path('restaurant/register/', views.register_restaurant_view, name='register_restaurant'),
    path('restaurant/login/', auth_views.LoginView.as_view(
        template_name='producers/login.html',
        authentication_form=RestaurantLoginForm,
        redirect_authenticated_user=True,
        extra_context={'title': 'Restaurant Login'},
        next_page='/',
    ), name='restaurant_login'),

    # producer profile page
    path('producer/products/', views.myproduct_view, name="myproduct"),
    path('producer/products/add/', views.addproduct_view, name="add_product"),
    path('producer/products/delete/<int:product_id>/', views.delete_product, name='delete_product'),
    path('producer/products/<int:product_id>/edit/', views.product_edit_view, name='edit_product'),

    path('producer/orders/', views.incoming_orders_view, name='incoming_orders'),
    path('producer/orders/update/<int:order_id>/', views.update_order_status, name='update_order_status'),
    path('producer/orders/<int:order_id>/', views.order_detail, name='order_detail'),

    path('producer/quality-scan', views.quality_scan_view, name='quality_scan'),

    path('producer/profile/', views.producer_profile_view, name='profile'),
    path("producer/profile/personal-info", views.personal_info_view, name="personal_info"),

    # TC-019: Surplus deals
    path('producer/products/<int:product_id>/surplus/', views.mark_surplus, name='mark_surplus'),
    path('producer/products/<int:product_id>/surplus/remove/', views.remove_surplus, name='remove_surplus'),

    # TC-020: Content management (recipes & farm stories)
    path('producer/content/', views.content_dashboard, name='content'),
    path('producer/content/recipes/add/', views.add_recipe, name='add_recipe'),
    path('producer/content/recipes/<int:recipe_id>/edit/', views.edit_recipe, name='edit_recipe'),
    path('producer/content/recipes/<int:recipe_id>/delete/', views.delete_recipe, name='delete_recipe'),
    path('producer/content/stories/add/', views.add_farm_story, name='add_farm_story'),
    path('producer/content/stories/<int:story_id>/delete/', views.delete_farm_story, name='delete_farm_story'),
]