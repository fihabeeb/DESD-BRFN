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
    path('orders/', include("orders.urls",namespace='orders'))

]