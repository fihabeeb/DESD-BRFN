"""
Recommendation service for V6 hard negative model with intelligent ordering.

Key features:
- Uses V6 model (hard negatives trained)
- Frequently Ordered: Products bought 2+ times shown as "Buy Again" quick options
- Amplification: Frequent purchases get boosted confidence
- Quick Re-order: Streamlined "one-click" reorder for recurring purchases
- Hybrid scoring: (model_score × 0.4) + (freq_score × 0.4) + (recency × 0.2)
"""
import pickle
import numpy as np
import logging
from collections import Counter
from products.models import Product
from django.db import models

logger = logging.getLogger(__name__)


class LSTMServiceV6:
    """Service for V6 hard negative model with intelligent ordering."""
    
    _instance = None
    _model = None
    _mappings = None
    
    FREQ_PURCHASE_THRESHOLD = 2
    MODEL_WEIGHT = 0.4
    FREQ_WEIGHT = 0.4
    RECENCY_WEIGHT = 0.2
    
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
                model_path="ml/recommendation/final/sigmoid_v6.keras",
                mappings_path="ml/recommendation/final/sigmoid_v6_mappings.pkl"):
        """Load V6 model and mappings."""
        try:
            from tensorflow.keras.models import load_model
            
            self._model = load_model(model_path)
            
            with open(mappings_path, 'rb') as f:
                self._mappings = pickle.load(f)
            
            logger.info(f"V6 model loaded: {len(self._mappings.get('p2i', {}))} products")
            
        except Exception as e:
            logger.error(f"Failed to load V6 model: {e}")
            self._model = None
    
    def get_recommendations(self, user_id, purchase_history_with_timestamps, top_k=5):
        """
        Get recommendations with intelligent ordering (frequency-based + amplification).
        
        Features:
        1. Frequently Ordered: Products bought 2+ times = "Buy Again" quick options
        2. Amplification: Frequent purchases get boosted confidence
        3. Quick Re-order: Streamlined reorder for recurring purchases
        
        Args:
            user_id: int
            purchase_history_with_timestamps: list of (product_id, datetime) tuples
            top_k: number of recommendations
            
        Returns:
            dict: {
                'recommended': [...],
                'quick_reorder': [...],  # Products bought multiple times
                'personalized': [...]     # Model predictions
            }
        """
        if not self._model:
            logger.warning("V6 model not loaded")
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
            
            # Build purchase frequency map
            purchase_counts = Counter([pid for pid, _ in purchase_history_with_timestamps])
            
            # Get frequently ordered products (threshold = 2+ purchases)
            frequent_products = {
                pid: count for pid, count in purchase_counts.items() 
                if count >= self.FREQ_PURCHASE_THRESHOLD
            }
            
            orders_map = {}
            for product_id, timestamp in purchase_history_with_timestamps:
                order_key = timestamp
                if order_key not in orders_map:
                    orders_map[order_key] = []
                orders_map[order_key].append((product_id, timestamp))
            
            sorted_orders = sorted(orders_map.keys())
            
            context_products = []
            context_timestamps = []
            
            recent_orders = sorted_orders[-max_order_history:]
            
            for ts in recent_orders:
                order_prods = orders_map[ts]
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
            
            while len(context_products) < max_order_history:
                context_products = [[0] * max_items_per_order] + context_products
                context_timestamps = [[0, 0]] + context_timestamps
            
            product_seq = [p for order_prods in context_products for p in order_prods]
            time_seq = context_timestamps
            
            prod_input = np.array([product_seq], dtype=np.int32)
            time_input = np.array([time_seq], dtype=np.float32)
            
            cluster_id = user_to_cluster.get(user_id, 0)
            user_cluster = np.array([[cluster_id]], dtype=np.int32)
            
            import tensorflow as tf
            logits = self._model.predict(
                [prod_input, time_input, user_cluster],
                verbose=0
            )[0]
            
            probs = tf.nn.softmax(logits, axis=-1).numpy()
            
            final_scores = self._apply_intelligent_scoring(
                purchase_history_with_timestamps,
                probs,
                idx_to_product,
                purchase_counts
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
                    
                    purchase_count = purchase_counts.get(product_id, 0)
                    is_frequent = purchase_count >= self.FREQ_PURCHASE_THRESHOLD
                    
                    recommended.append({
                        'product': product,
                        'score': float(score),
                        'probability': float(score),
                        'rank': len(recommended) + 1,
                        'confidence': 'frequent' if is_frequent else f"#{len(recommended) + 1}",
                        'purchase_count': purchase_count,
                        'quick_reorder_available': is_frequent
                    })
                except Product.DoesNotExist:
                    pass
            
            # Build quick reorder list (frequently purchased items)
            quick_reorder = self._get_quick_reorder(frequent_products, seen_products, top_k=5)
            
            # Build personalized recommendations (model predictions, excluding frequent)
            personalized = [r for r in recommended if not r.get('quick_reorder_available')]
            
            return {
                'recommended': recommended[:top_k],
                'quick_reorder': quick_reorder,
                'personalized': personalized[:top_k]
            }
            
        except Exception as e:
            logger.error(f"Error in V6 recommendation: {e}", exc_info=True)
            return self._get_popular_recommendations(top_k)
    
    def _extract_temporal_features(self, timestamp):
        """Extract temporal features from datetime."""
        day_of_week = timestamp.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0
        return [day_of_week, is_weekend]
    
    def _apply_intelligent_scoring(self, purchase_history, model_probs, idx_to_product, purchase_counts):
        """
        Apply intelligent scoring combining model, frequency, and recency.
        
        Hybrid scoring:
        - model_score × 0.4 (ML predictions)
        - freq_score × 0.4 (purchase frequency - amplification)
        - recency × 0.2 (recent purchases weighted more)
        
        This amplifies confidence for frequently purchased items, enabling
        quick re-order while still providing personalized suggestions.
        """
        if not purchase_history:
            final_scores = {}
            for idx in range(len(model_probs)):
                final_scores[idx] = model_probs[idx]
            return final_scores
        
        orders_map = {}
        for product_id, timestamp in purchase_history:
            order_key = timestamp
            if order_key not in orders_map:
                orders_map[order_key] = []
            orders_map[order_key].append(product_id)
        
        sorted_timestamps = sorted(orders_map.keys())
        if not sorted_timestamps:
            final_scores = {i: model_probs[i] for i in range(len(model_probs))}
            return final_scores
        
        num_orders = len(sorted_timestamps)
        
        # Calculate frequency score (normalized 0-1)
        max_freq = max(purchase_counts.values()) if purchase_counts else 1
        freq_scores = {pid: count / max_freq for pid, count in purchase_counts.items()}
        
        # Calculate recency score (exponential decay)
        product_recency = {}
        for position_from_end, ts in enumerate(reversed(sorted_timestamps)):
            weight = 0.7 ** position_from_end
            for product_id in orders_map[ts]:
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
            freq_score = freq_scores.get(product_id, 0.0)
            recency_score = product_recency.get(product_id, 0.0)
            
            # Apply amplification for frequently purchased items
            freq_boost = 1.0
            if freq_score >= self.FREQ_PURCHASE_THRESHOLD / max_freq:
                freq_boost = 1.5
            
            combined = (
                self.MODEL_WEIGHT * model_score +
                self.FREQ_WEIGHT * freq_score * freq_boost +
                self.RECENCY_WEIGHT * recency_score
            )
            
            final_scores[idx] = combined
        
        return final_scores
    
    def _get_quick_reorder(self, frequent_products, exclude_products, top_k=5):
        """
        Get quick reorder options for frequently purchased items.
        
        These are products the user has bought 2+ times - ideal for
        one-click reordering (quick convenience).
        
        Returns:
            list of dict: [{'product': Product, 'score': float, 'purchase_count': int}, ...]
        """
        if not frequent_products:
            return []
        
        sorted_by_freq = sorted(
            frequent_products.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        quick_reorder = []
        for product_id, count in sorted_by_freq:
            if len(quick_reorder) >= top_k:
                break
            if product_id in exclude_products:
                continue
            
            try:
                product = Product.objects.get(
                    id=product_id,
                    availability='available'
                )
                quick_reorder.append({
                    'product': product,
                    'score': float(count),
                    'purchase_count': count,
                    'confidence': 'quick_reorder'
                })
            except Product.DoesNotExist:
                pass
        
        return quick_reorder
    
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