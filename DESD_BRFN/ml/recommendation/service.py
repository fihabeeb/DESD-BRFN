# ml/recommendation/service.py

from ml.recommendation.model import load_trained_model, recommend_next_products
from products.models import Product
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for generating product recommendations using LSTM model"""
    
    def __init__(self):
        """Initialize the recommendation service with trained model"""
        self.model = None
        self.product_to_idx = None
        self.idx_to_product = None
        self.sequence_length = None
        self.load_model()
    
    def load_model(self):
        """Load the trained model and mappings with caching"""
        try:
            # Try to load from cache first (optional)
            cache_key = 'recommendation_model'
            cached = cache.get(cache_key)
            
            if cached:
                self.model, self.product_to_idx, self.idx_to_product, self.sequence_length = cached
                logger.info("Recommendation model loaded from cache")
            else:
                self.model, self.product_to_idx, self.idx_to_product, self.sequence_length = load_trained_model()
                # Cache for 1 hour (adjust as needed)
                cache.set(cache_key, (self.model, self.product_to_idx, self.idx_to_product, self.sequence_length), 3600)
                logger.info("Recommendation model loaded from disk")
                
        except Exception as e:
            logger.error(f"Failed to load recommendation model: {e}")
            # Model not trained yet - service will return empty recommendations
            self.model = None
    
    def get_recommendations(self, user_id, purchase_history, top_k=5):
        """
        Get product recommendations for a user
        
        Args:
            user_id: User ID (for logging)
            purchase_history: List of recent product IDs
            top_k: Number of recommendations to return
        
        Returns:
            List of product objects with scores
        """
        # Return empty list if model isn't loaded
        if not self.model:
            logger.warning("Recommendation model not available")
            return []
        
        # Return empty list if no purchase history
        if not purchase_history:
            logger.info(f"No purchase history for user {user_id}")
            return []
        
        try:
            # Get recommended product IDs with probabilities
            recommendations = recommend_next_products(
                self.model,
                self.product_to_idx,
                self.idx_to_product,
                purchase_history,
                top_k=top_k
            )
            
            # Fetch actual product objects
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
                    logger.warning(f"Recommended product {product_id} not found or unavailable")
                    continue
            
            logger.info(f"Generated {len(recommended_products)} recommendations for user {user_id}")
            return recommended_products
            
        except Exception as e:
            logger.error(f"Error generating recommendations for user {user_id}: {e}")
            return []
    
    def get_recommendations_async(self, user_id, purchase_history, top_k=5):
        """
        Async version for AJAX calls - returns serialized data
        """
        recommendations = self.get_recommendations(user_id, purchase_history, top_k)
        
        # Serialize for JSON response
        return [{
            'id': rec['product'].id,
            'name': rec['product'].name,
            'price': float(rec['product'].price),
            'unit': rec['product'].unit,
            'score': rec['score'],
            'confidence': rec['confidence'],
            'image_url': rec['product'].image.url if hasattr(rec['product'], 'image') and rec['product'].image else None,
        } for rec in recommendations]


# Optional: Cache warming function
def warm_recommendation_cache():
    """Pre-load the model into cache for faster response"""
    service = RecommendationService()
    logger.info("Recommendation model cached and ready")