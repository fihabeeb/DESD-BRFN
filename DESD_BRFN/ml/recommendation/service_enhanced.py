# ml/recommendation/service.py
import pickle

from ml.recommendation.model_enhanced import recommend_next_products_enhanced
from products.models import Product
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class EnhancedRecommendationService:
    """Service for generating recommendations with temporal awareness"""
    
    _instance = None
    _model = None
    user_to_idx = None
    _product_to_idx = None
    _idx_to_product = None
    _sequence_length = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        pass

    @classmethod
    def get_instance(cls):
        """Get or create the singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def load_model(self):
        """Load the enhanced model and mappings"""
        try:
            from tensorflow.keras.models import load_model
            
            self._model = load_model("ml/recommendation/final/recommendation_model_enhanced.keras")
            
            with open("ml/recommendation/product_mappings_enhanced.pkl", "rb") as f:
                mappings = pickle.load(f)
            
            self._product_to_idx = mappings["product_to_idx"]
            self._idx_to_product = mappings["idx_to_product"]
            self._sequence_length = mappings.get("sequence_length", 3)
            
            logger.info("Enhanced recommendation model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load enhanced recommendation model: {e}")
            self._model = None

    def get_recommendations(self, user_id, purchase_history_with_timestamps, top_k=5):
        """
        Get recommendations using both product history and timestamps
        """
        if not self._model:
            logger.warning("Model not loaded")
            return []
        
        if not purchase_history_with_timestamps:
            logger.info(f"No purchase history for user {user_id}")
            return []
        
        try:
            # Validate input structure
            if not all(isinstance(item, (tuple, list)) and len(item) == 2 
                    for item in purchase_history_with_timestamps):
                logger.error(f"Invalid purchase history format for user {user_id}")
                return []
            
            # Unzip the history
            product_ids = []
            timestamps = []
            
            for item in purchase_history_with_timestamps:
                product_ids.append(item[0])
                timestamps.append(item[1])
            
            logger.info(f"Processing {len(product_ids)} items for user {user_id}")
            logger.info("Calling recommend_next_products_enhanced...")
            
            recommendations = recommend_next_products_enhanced(
                self._model,
                self._product_to_idx,
                self._idx_to_product,
                product_ids,
                timestamps,
                user_id=user_id,
                user_to_idx=self.user_to_idx,
                top_k=top_k
            )
            
            logger.info(f"Got {len(recommendations)} raw recommendations")
            
            # Fetch product objects
            recommended_products = []
            for product_id, probability in recommendations:
                try:
                    product = Product.objects.get(id=product_id, availability='available')
                    recommended_products.append({
                        'product': product,
                        'score': probability,
                        'confidence': f"{probability:.1%}"
                    })
                except Product.DoesNotExist:
                    logger.warning(f"Product {product_id} not found")
                    continue
            
            logger.info(f"Returning {len(recommended_products)} products")
            return recommended_products
            
        except Exception as e:
            logger.error(f"Error generating enhanced recommendations: {e}", exc_info=True)
            return []