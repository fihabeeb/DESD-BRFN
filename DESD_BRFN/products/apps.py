from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'

    def ready(self):
        try:
            from ml.recommendation.service_enhanced import EnhancedRecommendationService
            
            # Pre-load the model at startup
            service = EnhancedRecommendationService.get_instance()
            service.load_model()
            
            print("Recommendation model pre-loaded successfully")
            
        except Exception as e:
            print(f"Could not pre-load recommendation model: {e}")