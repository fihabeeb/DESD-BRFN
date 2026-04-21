from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'

    def ready(self):
        try:
            from ml.recommendation.sigmoid_service import LSTMServiceSigmoid

            service = LSTMServiceSigmoid.get_instance()
            service.load_model() 
            
        except Exception as e:
            print(f"Could not pre-load recommendation model: {e}")