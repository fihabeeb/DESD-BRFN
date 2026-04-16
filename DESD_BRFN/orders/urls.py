from django.urls import path
from . import views

app_name = 'orders'
urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),

    path('create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('success/', views.success, name='success'),
    path('cancel/', views.cancel, name='cancel'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),

    path('order-history/', views.order_history, name="order_history")
    path('history/', views.order_history, name="order_history"),

    # TC-018: Recurring orders management
    path('recurring/', views.recurring_orders_list, name='recurring_list'),
    path('recurring/<int:pk>/', views.recurring_order_detail, name='recurring_detail'),
    path('recurring/<int:pk>/pause/', views.pause_recurring_order, name='recurring_pause'),
    path('recurring/<int:pk>/resume/', views.resume_recurring_order, name='recurring_resume'),
    path('recurring/<int:pk>/cancel/', views.cancel_recurring_order, name='recurring_cancel'),
    path('recurring/instance/<int:pk>/edit/', views.edit_instance, name='recurring_edit_instance'),
]
