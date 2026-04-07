from django.urls import path
from . import views

app_name = 'orders'
urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),

    path('create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('success/', views.success, name='success'),
    path('cancel/', views.cancel, name='cancel'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
    path('history/', views.order_history, name="order_history")
]
