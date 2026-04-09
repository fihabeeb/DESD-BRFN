from django.urls import path
from . import views

app_name = 'payments'
urlpatterns = [
    path('settlements/history', views.payment_history, name='settlement_history'),
    path('settlements/<int:settlement_id>', views.settlement_detail, name='settlement_detail'),

    path('settlements/<int:settlement_id>/download/csv', views.download_settlement_csv, name='download_settlement_csv'),
    path('settlements/<int:settlement_id>/download/pdf', views.download_settlement_pdf, name='download_settlement_pdf'),

]
