"""
Recommendation service for V5 sampled softmax model with recency boosting.

Key features:
- Uses V5 model (sampled softmax trained)
- Applies recency bias: more recent orders weighted higher
- Exponential decay: recent purchases get more weight (0.7^n decay)
- Fusion: model_score * 0.5 + recency_score * 0.5
"""
import pickle
import numpy as np
import logging
from products.models import Product
from django.db import models

logger = logging.getLogger(__name__)


class LSTMServiceV5:
    """Service for V5 sampled softmax with recency."""
    
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
                model_path="ml/recommendation/final/sigmoid_v5.keras",
                mappings_path="ml/recommendation/final/sigmoid_v5_mappings.pkl"):
        """Load V5 model and mappings."""
        try:
            from tensorflow.keras.models import load_model
            
            self._model = load_model(model_path)
            
            with open(mappings_path, 'rb') as f:
                self._mappings = pickle.load(f)
            
            logger.info(f"V5 model loaded: {self._mappings.get('num_products', '?')} products")
            
        except Exception as e:
            logger.error(f"Failed to load V5 model: {e}")
            self._model = None
    
    def get_recommendations(self, user_id, purchase_history_with_timestamps, top_k=5):
        """
        Get recommendations with recency boosting.
        
        Args:
            user_id: int
            purchase_history_with_timestamps: list of (product_id, datetime) tuples
            top_k: number of recommendations
            
        Returns:
            list of dict: [{'product': Product, 'score': float, 'confidence': str}, ...]
        """
        if not self._model:
            logger.warning("V5 model not loaded")
            return self._get_popular_recommendations(top_k)
        
        if not purchase_history_with_timestamps:
            return self._get_popular_recommendations(top_k)
        
        try:
            mappings = self._mappings
            product_to_idx = mappings.get('p2i', mappings.get('product_to_idx', {}))
            idx_to_product = mappings.get('i2p', mappings.get('idx_to_product', {}))
            user_to_cluster = mappings.get('u2c', mappings.get('user_to_cluster', {}))
            max_order_history = mappings.get('max_order_history', 15)
            max_items_per_order = mappings.get('max_items_per_order', 10)
            other_token = mappings.get('other_token', 1)
            
            # Group purchases by order (timestamp)
            orders_map = {}
            for product_id, timestamp in purchase_history_with_timestamps:
                order_key = timestamp
                if order_key not in orders_map:
                    orders_map[order_key] = []
                orders_map[order_key].append((product_id, timestamp))
            
            # Sort oldest → newest
            sorted_orders = sorted(orders_map.keys())
            
            # Build context sequences
            context_products = []
            context_timestamps = []
            
            recent_orders = sorted_orders[-max_order_history:]
            
            for ts in recent_orders:
                order_prods = orders_map[ts]
                # Handle both tuple and non-tuple formats
                if order_prods and isinstance(order_prods[0], tuple):
                    prods_only = [p for p, _ in order_prods]
                else:
                    prods_only = list(order_prods)
                
                prods_only = prods_only[:max_items_per_order]
                
                if len(prods_only) < max_items_per_order:
                    prods_only = prods_only + [0] * (max_items_per_order - len(prods_only))
                
                encoded = [product_to_idx.get(p, other_token) if p != 0 else 0 for p in prods_only]
                context_products.append(encoded)
                
                context_timestamps.append(self._extract_temporal_features(ts))
            
            # Pad orders if needed
            while len(context_products) < max_order_history:
                context_products = [[0] * max_items_per_order] + context_products
                context_timestamps = [[0.0] * 5] + context_timestamps
            
            # Flatten
            product_seq = [p for order_prods in context_products for p in order_prods]
            time_seq = context_timestamps
            
            # Prepare inputs
            prod_input = np.array([product_seq], dtype=np.int32)
            time_input = np.array([time_seq], dtype=np.float32)
            
            # Get user cluster
            cluster_id = user_to_cluster.get(user_id, 0)
            user_cluster = np.array([[cluster_id]], dtype=np.int32)
            
            # Get model predictions
            import tensorflow as tf
            logits = self._model.predict(
                [prod_input, time_input, user_cluster],
                verbose=0
            )[0]
            
            # Apply softmax
            probs = tf.nn.softmax(logits, axis=-1).numpy()
            
            # Apply recency bias
            final_scores = self._apply_recency_bias(
                purchase_history_with_timestamps,
                probs,
                idx_to_product
            )
            
            # Sort by score
            sorted_indices = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)
            
            # Get top-K recommendations
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
                    recommended.append({
                        'product': product,
                        'score': float(score),
                        'probability': float(score),
                        'rank': len(recommended) + 1,
                        'confidence': f"#{len(recommended) + 1}"
                    })
                except Product.DoesNotExist:
                    pass
            
            return recommended
            
        except Exception as e:
            logger.error(f"Error in V5 recommendation: {e}", exc_info=True)
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
    
    def _apply_recency_bias(self, purchase_history, model_probs, idx_to_product):
        """
        Apply recency bias - more recent purchases get higher weight.
        
        Exponential decay: weight = 0.7^n where n = orders ago
        Recent orders (n=0): weight = 1.0
        1 order ago: weight = 0.7
        2 orders ago: weight = 0.49
        etc.
        """
        if not purchase_history:
            # No history - just use model scores
            final_scores = {}
            for idx in range(len(model_probs)):
                final_scores[idx] = model_probs[idx]
            return final_scores
        
        # Group by order
        orders_map = {}
        for product_id, timestamp in purchase_history:
            order_key = timestamp
            if order_key not in orders_map:
                orders_map[order_key] = []
            orders_map[order_key].append(product_id)
        
        # Sort oldest → newest
        sorted_timestamps = sorted(orders_map.keys())
        if not sorted_timestamps:
            final_scores = {i: model_probs[i] for i in range(len(model_probs))}
            return final_scores
        
        # Calculate recency weights (exponential decay)
        num_orders = len(sorted_timestamps)
        
        # Product to recency score
        product_recency = {}
        
        # More recent = higher weight (reverse order for calculation)
        for position_from_end, ts in enumerate(reversed(sorted_timestamps)):
            # position_from_end: 0 = most recent, 1 = second most recent, etc.
            weight = 0.7 ** position_from_end
            
            for product_id in orders_map[ts]:
                if product_id not in product_recency:
                    product_recency[product_id] = 0.0
                product_recency[product_id] += weight
        
        # Normalize recency scores
        total_recency = sum(product_recency.values())
        if total_recency > 0:
            for pid in product_recency:
                product_recency[pid] /= total_recency
        
        # Combine model predictions with recency
        final_scores = {}
        
        for idx in range(2, len(model_probs)):
            if idx not in idx_to_product:
                continue
            
            product_id = idx_to_product.get(idx)
            if not product_id:
                continue
            
            model_score = float(model_probs[idx])
            recency_score = product_recency.get(product_id, 0.0)
            
            # Fusion: 50% model + 50% recency
            # Boost products with recency more heavily for users with purchase history
            recency_boost = 0.5
            
            if recency_score > 0:
                # User has history - apply fusion
                combined = (1 - recency_boost) * model_score + recency_boost * recency_score * 2
                
                # Extra boost for very recent (top 3 orders)
                for recent_pos in range(min(3, num_orders)):
                    recent_order = sorted_timestamps[-(recent_pos + 1)]
                    if product_id in orders_map[recent_order]:
                        combined += 0.1 * (0.7 ** recent_pos)
            else:
                # New user - rely on model
                combined = model_score
            
            final_scores[idx] = combined
        
        return final_scores
    
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