import pickle
import logging
from products.models import Product
from ml.recommendation.sigmoid_model import recommend_next_items_sigmoid

logger = logging.getLogger(__name__)


class LSTMServiceSigmoid:
    """Service for multi‑label (sigmoid) recommendations."""

    _instance = None
    _model = None
    _product_to_idx = None
    _idx_to_product = None
    _user_to_idx = None
    _idx_to_user = None
    _max_seq_len = None
    _other_token = None
    _mappings = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_model(self,
                   model_path="ml/recommendation/final/sigmoid_lstm_fixed.keras",
                   mappings_path="ml/recommendation/final/sigmoid_mappings_fixed.pkl"):
        """Load the trained sigmoid model and mappings."""
        try:
            from tensorflow.keras.models import load_model

            self._model = load_model(model_path)#//, custom_objects={'loss': weighted_binary_crossentropy})

            with open(mappings_path, "rb") as f:
                self._mappings = pickle.load(f)

            self._product_to_idx = self._mappings["product_to_idx"]
            self._idx_to_product = self._mappings["idx_to_product"]
            self._user_to_idx = self._mappings["user_to_idx"]
            self._idx_to_user = self._mappings["idx_to_user"]
            self._max_seq_len = self._mappings.get("max_seq_len", 7)
            self._other_token = self._mappings.get("other_token", 1)

            logger.info("Fixed sigmoid LSTM model loaded successfully")
            logger.info(f"Max sequence length: {self._max_seq_len}, other_token: {self._other_token}")
        except Exception as e:
            logger.error(f"Failed to load fixed sigmoid model: {e}")
            self._model = None

    def get_recommendations(self, user_id, purchase_history_with_timestamps, top_k=5):
        """
        Get top‑k product recommendations for quick re‑order.

        Args:
            user_id: int
            purchase_history_with_timestamps: list of (product_id, datetime) tuples, chronological.
            top_k: number of recommendations to return

        Returns:
            list of dict: [{'product': Product, 'score': float, 'confidence': str}, ...]
        """
        if not self._model:
            logger.warning("Model not loaded. Call load_model() first.")
            return []

        if not purchase_history_with_timestamps:
            logger.info(f"No purchase history for user {user_id}")
            return []

        try:
            # Validate input
            if not all(isinstance(item, (tuple, list)) and len(item) == 2
                       for item in purchase_history_with_timestamps):
                logger.error(f"Invalid purchase history format for user {user_id}")
                return []

            product_ids = [item[0] for item in purchase_history_with_timestamps]
            timestamps = [item[1] for item in purchase_history_with_timestamps]

            logger.info(f"Generating recommendations for user {user_id} "
                        f"from {len(product_ids)} past purchases")

            # Call the fixed sigmoid recommendation function
            recommendations = recommend_next_items_sigmoid(
                user_id=user_id,
                user_history_products=product_ids,
                user_history_timestamps=timestamps,
                model=self._model,
                product_to_idx=self._product_to_idx,
                idx_to_product=self._idx_to_product,
                user_to_idx=self._user_to_idx,
                max_seq_len=self._max_seq_len,
                top_k=top_k,
                other_token=self._other_token
            )

            # Fetch actual Product objects
            recommended_products = []
            for product_id, probability in recommendations:
                try:
                    product = Product.objects.get(id=product_id, availability='available')
                    recommended_products.append({
                        'product': product,
                        'score': probability,
                        'confidence': f"{probability:.1%}"
                    })
                    
                    print(f"Recommending {product.name} with {probability:.1%} confidence")
                except Product.DoesNotExist:
                    logger.warning(f"Product {product_id} not found or unavailable")
                    continue

            logger.info(f"Returning {len(recommended_products)} recommendations")
            return recommended_products

        except Exception as e:
            logger.error(f"Error in fixed sigmoid recommendation service: {e}", exc_info=True)
            return []