from django.urls import path, include
from . import views

app_name = 'mainApp'

urlpatterns = [
    path('', views.home, name='home'),
    path('logout/', views.logout_view, name='logout'),

    path('profile/',views.profile_redirect, name="profile"),

    # treat this as main URL routing
    path('p/', include('producers.urls',namespace='producers'),),
    path('pt/', include('products.urls',namespace='products')),
    path('c/', include("customers.urls",namespace='customers')),
    path('orders/', include("orders.urls",namespace='orders')),
    path('payments/', include('payments.urls', namespace='payments')),



    # Address management
    path('user/manage-addresses/', views.manage_addresses, name='manage_addresses'),
    path('user/manage-addresses/add/', views.add_address, name='add_address'),
    path('user/manage-addresses/<int:address_id>/edit/', views.edit_address, name='edit_address'),
    path('user/manage-addresses/<int:address_id>/delete/', views.delete_address, name='delete_address'),
    path('user/manage-addresses/<int:address_id>/set-default/', views.set_default_address, name='set_default_address'),
]