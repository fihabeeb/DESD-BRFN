"""Thin HTTP client — delegates recommendations to the ml-service container."""
import os
import logging
import requests

logger = logging.getLogger(__name__)

ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml-service:8001")


class LSTMServiceSigmoid:
    """Drop-in replacement that calls the ml-service over HTTP."""

    _instance = None
    _sequence_length = 7

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_model(self):
        """No-op: model lives in the ml-service container."""
        pass

    @property
    def sequence_length(self):
        return self._sequence_length

    def get_recommendations(self, user_id, purchase_history_with_timestamps, top_k=5):
        """
        Args:
            purchase_history_with_timestamps: list of (product_id, datetime) tuples
        Returns:
            list of {'product': Product, 'score': float, 'confidence': str}
        """
        from products.models import Product

        if not purchase_history_with_timestamps:
            return []

        payload = {
            "user_id": user_id,
            "purchase_history": [
                {
                    "product_id": pid,
                    "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                }
                for pid, ts in purchase_history_with_timestamps
            ],
            "top_k": top_k,
        }

        try:
            response = requests.post(
                f"{ML_SERVICE_URL}/predict/recommendations",
                json=payload,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error("ml-service recommendation request failed: %s", e)
            return []

        self._sequence_length = data.get("max_seq_len", self._sequence_length)

        results = []
        for item in data.get("recommendations", []):
            try:
                product = Product.objects.get(id=item["product_id"], availability="available")
                results.append(
                    {
                        "product": product,
                        "score": item["score"],
                        "confidence": item["confidence"],
                    }
                )
            except Product.DoesNotExist:
                logger.warning("Recommended product %s not found or unavailable", item["product_id"])

        return results
