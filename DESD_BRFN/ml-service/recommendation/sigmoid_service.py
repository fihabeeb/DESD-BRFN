import os
import pickle
import logging
from recommendation.sigmoid_model import recommend_next_items_sigmoid

logger = logging.getLogger(__name__)

MODEL_PATH = os.environ.get(
    "RECOMMENDATION_MODEL_PATH",
    "ml/recommendation/final/sigmoid_lstm.keras",
)
MAPPINGS_PATH = os.environ.get(
    "RECOMMENDATION_MAPPINGS_PATH",
    "ml/recommendation/final/sigmoid_mappings.pkl",
)


class RecommendationService:
    def __init__(self):
        self._model = None
        self._product_to_idx = None
        self._idx_to_product = None
        self._user_to_idx = None
        self._max_seq_len = 7
        self._other_token = 1

    def is_loaded(self) -> bool:
        return self._model is not None

    def load_model(self):
        try:
            from tensorflow.keras.models import load_model
            self._model = load_model(MODEL_PATH)

            with open(MAPPINGS_PATH, "rb") as f:
                mappings = pickle.load(f)

            self._product_to_idx = mappings["product_to_idx"]
            self._idx_to_product = mappings["idx_to_product"]
            self._user_to_idx = mappings["user_to_idx"]
            self._max_seq_len = mappings.get("max_seq_len", 7)
            self._other_token = mappings.get("other_token", 1)

            logger.info("Recommendation model loaded (max_seq_len=%s)", self._max_seq_len)
        except Exception as e:
            logger.error("Failed to load recommendation model: %s", e)
            self._model = None

    def get_recommendations(self, user_id: int, purchase_history: list, top_k: int = 5) -> list:
        """
        Args:
            purchase_history: list of {"product_id": int, "timestamp": datetime | list[float]}
        Returns:
            list of {"product_id": int, "score": float, "confidence": str}
        """
        if not self._model:
            logger.warning("Recommendation model not loaded")
            return []
        if not purchase_history:
            return []

        product_ids = [item["product_id"] for item in purchase_history]
        timestamps = [item["timestamp"] for item in purchase_history]

        raw = recommend_next_items_sigmoid(
            user_id=user_id,
            user_history_products=product_ids,
            user_history_timestamps=timestamps,
            model=self._model,
            product_to_idx=self._product_to_idx,
            idx_to_product=self._idx_to_product,
            user_to_idx=self._user_to_idx,
            max_seq_len=self._max_seq_len,
            top_k=top_k,
            other_token=self._other_token,
        )

        return [
            {"product_id": pid, "score": score, "confidence": f"{score:.1%}"}
            for pid, score in raw
        ]

    @property
    def max_seq_len(self) -> int:
        return self._max_seq_len

    @property
    def model_path(self) -> str:
        return MODEL_PATH

    @property
    def mappings_path(self) -> str:
        return MAPPINGS_PATH
