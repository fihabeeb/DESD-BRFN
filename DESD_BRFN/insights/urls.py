from django.urls import path
from . import views

urlpatterns = [
    path('', views.insights_index, name='insights_index'),
    path('recommendations/', views.recommendation_insights, name='insights_recommendations'),
    path('classification/', views.classification_insights, name='insights_classification'),
    path('models/upload/', views.upload_model, name='insights_upload_model'),
]
