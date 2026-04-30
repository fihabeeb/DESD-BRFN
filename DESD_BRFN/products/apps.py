from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'

    def ready(self):
        try:

            from ml.recommendation.sigmoid_service_v5 import LSTMServiceV5

            service = LSTMServiceV5.get_instance()
            service.load_model()

            # from ml.recommendation.sigmoid_service_v5_1 import LSTMServiceV5_1

            # service = LSTMServiceV5_1.get_instance()
            # service.load_model()

        except Exception as e:
            print(f"Could not pre-load recommendation model: {e}")
