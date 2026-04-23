"""
Recommendation service for simplified sigmoid LSTM model (v3).
Uses recency bias to personalize recommendations.
"""
import pickle
import numpy as np
import logging
import django
from products.models import Product
from django.db import models

logger = logging.getLogger(__name__)


class LSTMServiceV3:
    """Service for simplified model v3 recommendations."""
    
    _instance = None
    _model = None
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
                model_path="ml/recommendation/final/sigmoid_v3.keras",
                mappings_path="ml/recommendation/final/sigmoid_v3_mappings.pkl"):
        """Load the simplified v3 model and mappings."""
        try:
            from tensorflow.keras.models import load_model
            
            self._model = load_model(model_path)
            
            with open(mappings_path, 'rb') as f:
                self._mappings = pickle.load(f)
            
            logger.info(f"V3 model loaded: {self._mappings.get('num_products')} products")
            logger.info(f"Optimal threshold: {self._mappings.get('optimal_threshold', 0.25)}")
            
        except Exception as e:
            logger.error(f"Failed to load v3 model: {e}")
            self._model = None
    
    def get_recommendations(self, user_id, purchase_history_with_timestamps, top_k=5):
        """
        Get order-level recommendations with recency bias.
        
        Args:
            user_id: int
            purchase_history_with_timestamps: list of (product_id, datetime) tuples
            top_k: number of recommendations
            
        Returns:
            list of dict: [{'product': Product, 'score': float, 'confidence': str}, ...]
        """
        if not self._model:
            logger.warning("V3 model not loaded")
            return self._get_popular_recommendations(top_k)
        
        if not purchase_history_with_timestamps:
            return self._get_popular_recommendations(top_k)
        
        try:
            mappings = self._mappings
            product_to_idx = mappings['product_to_idx']
            idx_to_product = mappings['idx_to_product']
            user_to_cluster = mappings.get('user_to_cluster', {})
            max_order_history = mappings.get('max_order_history', 15)
            max_items_per_order = mappings.get('max_items_per_order', 10)
            other_token = mappings.get('other_token', 1)
            threshold = mappings.get('optimal_threshold', 0.25)
            
            orders_map = {}
            for product_id, timestamp in purchase_history_with_timestamps:
                order_key = timestamp
                if order_key not in orders_map:
                    orders_map[order_key] = []
                orders_map[order_key].append((product_id, timestamp))
            
            sorted_orders = sorted(orders_map.items(), key=lambda x: x[0])
            
            context_products = []
            context_timestamps = []
            
            recent_orders = sorted_orders[-max_order_history:]
            
            for ts, order_prods in recent_orders:
                order_prods = list(order_prods)[:max_items_per_order]
                
                if len(order_prods) < max_items_per_order:
                    order_prods = order_prods + [0] * (max_items_per_order - len(order_prods))
                
                encoded = [product_to_idx.get(p, other_token) if p != 0 else 0 for p in order_prods]
                context_products.append(encoded)
                
                context_timestamps.append(self._extract_temporal_features(ts))
            
            while len(context_products) < max_order_history:
                context_products = [[0] * max_items_per_order] + context_products
                context_timestamps = [[0.0] * 5] + context_timestamps
            
            product_seq = [p for order_prods in context_products for p in order_prods]
            time_seq = context_timestamps
            
            prod_input = np.array([product_seq], dtype=np.int32)
            time_input = np.array([time_seq], dtype=np.float32)
            
            cluster_id = user_to_cluster.get(user_id, 0)
            user_cluster = np.array([[cluster_id]], dtype=np.int32)
            
            predictions = self._model.predict(
                [prod_input, time_input, user_cluster],
                verbose=0
            )[0]
            
            final_scores = self._apply_recency_bias(
                purchase_history_with_timestamps,
                predictions,
                idx_to_product,
                threshold
            )
            
            sorted_indices = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)
            
            recommended = []
            seen_products = set()
            
            for idx in sorted_indices:
                if len(recommended) >= top_k:
                    break
                
                score = final_scores[idx]
                
                product_id = idx_to_product.get(idx)
                if not product_id or product_id in seen_products:
                    continue
                
                seen_products.add(product_id)
                
                try:
                    product = Product.objects.get(
                        id=product_id, 
                        availability='available'
                    )
                    score_val = float(score)
                    recommended.append({
                        'product': product,
                        'score': score_val,
                        'probability': score_val,
                        'rank': len(recommended) + 1,
                        'confidence': f"#{len(recommended) + 1}"
                    })
                except Product.DoesNotExist:
                    pass
            
            return recommended
            
        except Exception as e:
            logger.error(f"Error in v3 recommendation: {e}", exc_info=True)
            return []
    
    def _extract_temporal_features(self, timestamp):
        """Extract temporal features from datetime."""
        day_of_week = timestamp.weekday()
        day_sin = np.sin(2 * np.pi * day_of_week / 7.0)
        day_cos = np.cos(2 * np.pi * day_of_week / 7.0)
        month = timestamp.month
        month_sin = np.sin(2 * np.pi * month / 12.0)
        month_cos = np.cos(2 * np.pi * month / 12.0)
        is_weekend = 1.0 if day_of_week >= 5 else 0.0
        return [day_sin, day_cos, month_sin, month_cos, is_weekend]
    
    def _get_popular_recommendations(self, top_k=5):
        """Fallback for users with no history."""
        from products.models import Product
        from orders.models import OrderItem
        from django.db.models import Count
        
        popular_ids = OrderItem.objects.filter(
            producer_order__payment__payment_status='paid',
            product__availability='available'
        ).values_list('product_id', flat=True).annotate(
            count=Count('id')
        ).order_by('-count')[:top_k]
        
        recommended = []
        for product_id in popular_ids:
            try:
                product = Product.objects.get(id=product_id, availability='available')
                recommended.append({
                    'product': product,
                    'score': 1.0,
                    'confidence': 'popular'
                })
            except Product.DoesNotExist:
                pass
        
        return recommended
    
    def _apply_recency_bias(self, purchase_history, predictions, idx_to_product, threshold):
        """
        Apply recency bias - boost products the user purchased recently.
        """
        if not purchase_history:
            final_scores = {}
            for idx in range(2, len(predictions)):
                final_scores[idx] = predictions[idx]
            return final_scores
        
        orders_map = {}
        for product_id, timestamp in purchase_history:
            order_key = timestamp
            if order_key not in orders_map:
                orders_map[order_key] = []
            orders_map[order_key].append((product_id, timestamp))
        
        sorted_orders = sorted(orders_map.keys())
        if not sorted_orders:
            final_scores = {}
            for idx in range(2, len(predictions)):
                final_scores[idx] = predictions[idx]
            return final_scores
        
        all_products = []
        for order_prods in orders_map.values():
            for product_id, _ in order_prods:
                all_products.append(product_id)
        
        max_history = min(len(sorted_orders), 15)
        
        recency_weights = {}
        for i, order_ts in enumerate(sorted_orders[-max_history:]):
            position_from_end = max_history - 1 - i
            weight = 0.7 ** position_from_end
            recency_weights[order_ts] = weight
        
        total_weight = sum(recency_weights.values())
        if total_weight > 0:
            for ts in recency_weights:
                recency_weights[ts] /= total_weight
        
        product_recency_scores = {}
        for order_ts, order_prods in orders_map.items():
            weight = recency_weights.get(order_ts, 0)
            for product_id, _ in order_prods:
                if product_id not in product_recency_scores:
                    product_recency_scores[product_id] = 0.0
                product_recency_scores[product_id] += weight
        
        final_scores = {}
        for idx in range(2, len(predictions)):
            product_id = idx_to_product.get(idx)
            if not product_id:
                continue
            
            model_score = float(predictions[idx])
            recency_score = product_recency_scores.get(product_id, 0.0)
            
            recency_boost = 0.35
            combined_score = (1 - recency_boost) * model_score + recency_boost * recency_score * 2.0
            
            if product_id in all_products:
                for i, order_ts in enumerate(sorted_orders):
                    if product_id in [p for p, _ in orders_map[order_ts]]:
                        recent_factor = 0.7 ** (len(sorted_orders) - 1 - i)
                        combined_score += 0.15 * recent_factor
                        break
            
            if combined_score >= threshold * 0.5:
                final_scores[idx] = combined_score
        
        if not final_scores:
            for idx in range(2, len(predictions)):
                final_scores[idx] = predictions[idx]
        
        return final_scores