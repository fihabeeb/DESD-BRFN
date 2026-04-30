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
    
    def get_recommendations(self, user_id, top_k=5):
        """
        Get recommendations with recency boosting.
        
        Args:
            user_id: int
            top_k: number of recommendations
            
        Returns:
            dict with 'recommendations' list and metadata
        """
        history = self.get_user_purchase_history(user_id=user_id, max_orders=15)
        
        if not self._model:
            logger.warning("V5 model not loaded")
            return {
                'recommendations': self._get_popular_recommendations(top_k),
                'num_orders': 0
            }
        
        if not history or len(history) < 1:
            return {
                'recommendations': self._get_popular_recommendations(top_k),
                'num_orders': 0
            }
        
        try:
            mappings = self._mappings
            product_to_idx = mappings.get('p2i', {})
            idx_to_product = mappings.get('i2p', {})
            user_to_cluster = mappings.get('u2c', {})
            
            max_order_history = mappings.get('max_order', mappings.get('max_orders', 15))
            max_items_per_order = mappings.get('max_items', 5)
            
            sorted_order_ids = sorted(history.keys(), key=lambda x: history[x]['timestamp'])
            
            context_products = []
            context_timestamps = []
            
            for order_id in sorted_order_ids[-max_order_history:]:
                order = history[order_id]
                prods = order['products'][:max_items_per_order]
                
                if len(prods) < max_items_per_order:
                    prods = prods + [0] * (max_items_per_order - len(prods))
                
                encoded = [product_to_idx.get(p, 1) if p != 0 else 0 for p in prods]
                context_products.append(encoded)
                context_timestamps.append(self._extract_temporal_features(order['timestamp']))
            
            while len(context_products) < max_order_history:
                context_products = [[0] * max_items_per_order] + context_products
                context_timestamps = [[0.0] * 5] + context_timestamps
            
            prod_input = np.array([context_products], dtype=np.int32)
            time_input = np.array([context_timestamps], dtype=np.float32)
            
            cluster_id = user_to_cluster.get(user_id, 0)
            user_cluster = np.array([[cluster_id]], dtype=np.int32)
            
            import tensorflow as tf
            logits = self._model.predict(
                [prod_input, time_input, user_cluster],
                verbose=0
            )[0]
            
            probs = tf.nn.softmax(logits, axis=-1).numpy()
            
            final_scores = self._apply_recency_bias(
                history,
                probs,
                idx_to_product
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
                    recommended.append({
                        'product': product,
                        'score': float(score),
                        'probability': float(score),
                        'rank': len(recommended) + 1,
                        'confidence': f"#{len(recommended) + 1}"
                    })
                except Product.DoesNotExist:
                    pass
            
            return {
                'recommendations': recommended,
                'num_orders': len(history)
            }
            
        except Exception as e:
            logger.error(f"Error in V5 recommendation: {e}", exc_info=True)
            return {
                'recommendations': [],
                'num_orders': 0
            }
    
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
    
    def _apply_recency_bias(self, history, model_probs, idx_to_product):
        """
        Apply recency bias - more recent purchases get higher weight.
        
        Args:
            history: dict {order_id: {'timestamp': datetime, 'products': [pids]}}
            model_probs: array of prediction probabilities
            idx_to_product: mapping from index to product_id
            
        Exponential decay: weight = 0.7^n where n = orders ago
        """
        if not history:
            final_scores = {}
            for idx in range(len(model_probs)):
                final_scores[idx] = model_probs[idx]
            return final_scores
        
        sorted_order_ids = sorted(history.keys(), key=lambda x: history[x]['timestamp'])
        
        if not sorted_order_ids:
            final_scores = {i: model_probs[i] for i in range(len(model_probs))}
            return final_scores
        
        num_orders = len(sorted_order_ids)
        
        product_recency = {}
        
        for position_from_end, order_id in enumerate(reversed(sorted_order_ids)):
            weight = 0.7 ** position_from_end
            
            for product_id in history[order_id]['products']:
                if product_id not in product_recency:
                    product_recency[product_id] = 0.0
                product_recency[product_id] += weight
        
        total_recency = sum(product_recency.values())
        if total_recency > 0:
            for pid in product_recency:
                product_recency[pid] /= total_recency
        
        final_scores = {}
        
        for idx in range(2, len(model_probs)):
            if idx not in idx_to_product:
                continue
            
            product_id = idx_to_product.get(idx)
            if not product_id:
                continue
            
            model_score = float(model_probs[idx])
            recency_score = product_recency.get(product_id, 0.0)
            
            recency_boost = 0.5
            
            if recency_score > 0:
                combined = (1 - recency_boost) * model_score + recency_boost * recency_score * 2
                
                for recent_pos in range(min(3, num_orders)):
                    recent_order_id = sorted_order_ids[-(recent_pos + 1)]
                    if product_id in history[recent_order_id]['products']:
                        combined += 0.1 * (0.7 ** recent_pos)
            else:
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
    
    def get_user_purchase_history(self, user_id, max_orders=15):
            """
            Fetch and prepare purchase history for a user from DB.
            
            Returns dict: {order_id: {'timestamp': datetime, 'products': [product_ids]}}
            Ordered oldest to newest.
            """
            from orders.models import OrderItem
            
            order_items = OrderItem.objects.filter(
                producer_order__payment__user=user_id,
                producer_order__payment__payment_status="paid",
            ).select_related(
                'product', 
                'producer_order__payment'
            ).order_by(
                'producer_order__payment__created_at',
                'producer_order__id'
            )
            
            orders_map = {}
            for item in order_items:
                order_id = item.producer_order.id
                ts = item.producer_order.payment.created_at
                
                if order_id not in orders_map:
                    orders_map[order_id] = {'timestamp': ts, 'products': []}
                
                for _ in range(item.quantity):
                    orders_map[order_id]['products'].append(item.product.id)

            sorted_orders = sorted(orders_map.keys(), key=lambda x: orders_map[x]['timestamp'])
            
            if max_orders and len(sorted_orders) > max_orders:
                sorted_orders = sorted_orders[-max_orders:]
            
            return {oid: orders_map[oid] for oid in sorted_orders}