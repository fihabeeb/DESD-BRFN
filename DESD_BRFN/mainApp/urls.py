from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('logout/', views.logout_view, name='logout'),

    path('profile/',views.profile_redirect, name="profile"),

    # treat this as main URL routing
    path('', include('producers.urls')),
    path('', include('products.urls')),

]