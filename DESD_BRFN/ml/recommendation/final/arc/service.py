import pickle
import logging
from products.models import Product
from ml.recommendation.final.arc.models import recommend_next_items_lstm_attention

logger = logging.getLogger(__name__)


class LSTMSAttention:

    _instance = None
    _model = None
    _product_to_idx = None
    _idx_to_product = None
    _user_to_idx = None
    _idx_to_user = None
    _category_to_idx = None
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
                   model_path="ml/recommendation/final/lstm_attention.keras",
                   mappings_path="ml/recommendation/final/attention_mappings.pkl"):
        """Load the trained LSTM+Attention model and mappings."""
        try:
            from tensorflow.keras.models import load_model

            self._model = load_model(model_path)

            with open(mappings_path, "rb") as f:
                self._mappings = pickle.load(f)

            self._product_to_idx = self._mappings["product_to_idx"]
            self._idx_to_product = self._mappings["idx_to_product"]
            self._user_to_idx = self._mappings["user_to_idx"]
            self._idx_to_user = self._mappings["idx_to_user"]
            self._category_to_idx = self._mappings.get("category_to_idx", {})
            self._max_seq_len = self._mappings.get("max_seq_len", 20)
            self._other_token = self._mappings.get("other_token", 1)

            logger.info("LSTM+Attention model loaded successfully")
            logger.info(f"Max sequence length: {self._max_seq_len}, other_token: {self._other_token}")
        except Exception as e:
            logger.error(f"Failed to load LSTM+Attention model: {e}")
            self._model = None

    def get_recommendations(self, user_id, purchase_history_with_timestamps, top_k=5):
        """
        Get top‑k product recommendations based on long‑term interests.

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
            # Validate input format
            if not all(isinstance(item, (tuple, list)) and len(item) == 2
                       for item in purchase_history_with_timestamps):
                logger.error(f"Invalid purchase history format for user {user_id}")
                return []

            # Extract product IDs and timestamps
            product_ids = [item[0] for item in purchase_history_with_timestamps]
            timestamps = [item[1] for item in purchase_history_with_timestamps]

            # Fetch category for each product in history (optimize with a single query)
            products_with_cats = Product.objects.filter(id__in=product_ids).values_list('id', 'category_id')
            prod_to_cat = dict(products_with_cats)

            # Build category list parallel to product_ids (default to 0 if missing)
            categories = [prod_to_cat.get(pid, 0) for pid in product_ids]

            logger.info(f"Generating recommendations for user {user_id} "
                        f"from {len(product_ids)} past purchases")

            # Call the recommendation function
            recommendations = recommend_next_items_lstm_attention(
                user_id=user_id,
                user_history_products=product_ids,
                user_history_categories=categories,
                user_history_timestamps=timestamps,
                model=self._model,
                product_to_idx=self._product_to_idx,
                idx_to_product=self._idx_to_product,
                category_to_idx=self._category_to_idx,
                user_to_idx=self._user_to_idx,
                max_seq_len=self._max_seq_len,
                top_k=top_k,
                other_token=self._other_token
            )

            # Fetch actual Product objects for recommended IDs
            recommended_products = []
            for product_id, probability in recommendations:
                try:
                    product = Product.objects.get(id=product_id, availability='available')
                    recommended_products.append({
                        'product': product,
                        'score': probability,
                        'confidence': f"{probability:.1%}"
                    })
                    logger.debug(f"Recommending {product.name} with {probability:.1%} confidence")
                except Product.DoesNotExist:
                    logger.warning(f"Product {product_id} not found or unavailable")
                    continue

            logger.info(f"Returning {len(recommended_products)} recommendations for user {user_id}")
            return recommended_products

        except Exception as e:
            logger.error(f"Error in recommendation service: {e}", exc_info=True)
            return []