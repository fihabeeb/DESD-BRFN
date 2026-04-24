from django.urls import path
from . import views

app_name = 'interactions'

urlpatterns = [
    path('export/', views.export_csv, name='export_csv'),
    path('recommendation-click/<int:product_id>/', views.recommendation_click, name='recommendation_click'),
]
