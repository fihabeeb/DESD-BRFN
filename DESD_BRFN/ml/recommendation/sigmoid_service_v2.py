"""
Recommendation service for order-level sigmoid LSTM model (v2).
"""
import pickle
import numpy as np
import logging
import django
from products.models import Product
from django.db import models

logger = logging.getLogger(__name__)


class LSTMServiceOrderLevel:
    """Service for order-level (v2) recommendations."""
    
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
                 model_path="ml/recommendation/final/sigmoid_v2.keras",
                    mappings_path="ml/recommendation/final/sigmoid_v2_mappings.pkl"):
        """Load the order-level model and mappings."""
        try:
            from tensorflow.keras.models import load_model
            
            self._model = load_model(model_path)
            
            with open(mappings_path, 'rb') as f:
                self._mappings = pickle.load(f)
            
            # Load calibration if available
            self._caler = None
            cal_path = 'ml/recommendation/final/calibration.pkl'
            try:
                with open(cal_path, 'rb') as f:
                    cal_data = pickle.load(f)
                    self._caler = cal_data['caler']
            except Exception:
                pass
            
            logger.info(f"Order-level model loaded: {self._mappings.get('num_products')} products")
            logger.info(f"Calibration: {'loaded' if self._caler else 'none'}")
            
        except Exception as e:
            logger.error(f"Failed to load order-level model: {e}")
            self._model = None
    
    def get_recommendations(self, user_id, purchase_history_with_timestamps, top_k=5):
        """
        Get order-level recommendations.
        
        Args:
            user_id: int
            purchase_history_with_timestamps: list of (product_id, datetime) tuples
                Should be grouped by order - caller's responsibility
            top_k: number of recommendations
            
        Returns:
            list of dict: [{'product': Product, 'score': float, 'confidence': str}, ...]
        """
        if not self._model:
            logger.warning("Order-level model not loaded")
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
            
            # Group purchases by order
            orders_map = {}
            for product_id, timestamp in purchase_history_with_timestamps:
                order_key = timestamp
                if order_key not in orders_map:
                    orders_map[order_key] = []
                orders_map[order_key].append((product_id, timestamp))
            
            # Sort orders oldest → newest
            sorted_orders = sorted(orders_map.items(), key=lambda x: x[0])
            
            # Build input sequence (last max_order_history orders)
            context_products = []
            context_timestamps = []
            
            # Take only most recent max_order_history orders (oldest to newest)
            recent_orders = sorted_orders[-max_order_history:]
            
            for ts, order_prods in recent_orders:
                order_prods = list(order_prods)[:max_items_per_order]
                
                # Pad order to max_items_per_order
                if len(order_prods) < max_items_per_order:
                    order_prods = order_prods + [0] * (max_items_per_order - len(order_prods))
                
                encoded = [product_to_idx.get(p, other_token) if p != 0 else 0 for p in order_prods]
                context_products.append(encoded)
                
                # Get timestamp from sorted orders
                context_timestamps.append(self._extract_temporal_features(ts))
            
            # Pad orders if needed
            while len(context_products) < max_order_history:
                context_products = [[0] * max_items_per_order] + context_products
                context_timestamps = [[0.0] * 5] + context_timestamps
            
            # Flatten products
            product_seq = [p for order_prods in context_products for p in order_prods]
            time_seq = context_timestamps
            
            # Prepare inputs
            prod_input = np.array([product_seq], dtype=np.int32)
            time_input = np.array([time_seq], dtype=np.float32)
            
            # Get user cluster
            cluster_id = user_to_cluster.get(user_id, 0)
            user_cluster = np.array([[cluster_id]], dtype=np.int32)
            
            # Predict
            predictions = self._model.predict(
                [prod_input, time_input, user_cluster],
                verbose=0
            )[0]

            # Apply recency bias: boost products the user purchased recently
            final_scores = self._apply_recency_bias(
                purchase_history_with_timestamps,
                predictions,
                idx_to_product,
                threshold
            )

            # Sort by final score
            sorted_indices = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)
            
            # Get top-K recommendations using final_scores
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
            logger.error(f"Error in order-level recommendation: {e}", exc_info=True)
            return []
    
    def _extract_temporal_features(self, timestamp):
        """Extract temporal features from datetime."""
        import datetime
        day_of_week = timestamp.weekday()
        day_sin = np.sin(2 * np.pi * day_of_week / 7.0)
        day_cos = np.cos(2 * np.pi * day_of_week / 7.0)
        month = timestamp.month
        month_sin = np.sin(2 * np.pi * month / 12.0)
        month_cos = np.cos(2 * np.pi * month / 12.0)
        is_weekend = 1.0 if day_of_week >= 5 else 0.0
        return [day_sin, day_cos, month_sin, month_cos, is_weekend]
    
    def _get_popular_recommendations(self, top_k=5):
        """
        Fallback for users with no history - return popular products.
        not in use
        """
        from products.models import Product
        from orders.models import OrderItem
        from django.db.models import Count
        
        # Get most frequently ordered products
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
        Apply recency bias to boost products the user has purchased recently.
        
        Recent orders should be weighted more heavily - if user bought something
        recently, they're more likely to buy similar items again.
        """
        import datetime
        
        if not purchase_history:
            # No history - just use model predictions
            final_scores = {}
            for idx in range(2, len(predictions)):
                final_scores[idx] = predictions[idx]
            return final_scores
        
        # Group by order (timestamp)
        orders_map = {}
        for product_id, timestamp in purchase_history:
            order_key = timestamp
            if order_key not in orders_map:
                orders_map[order_key] = []
            orders_map[order_key].append((product_id, timestamp))
        
        # Sort oldest to newest
        sorted_orders = sorted(orders_map.keys())
        if not sorted_orders:
            final_scores = {}
            for idx in range(2, len(predictions)):
                final_scores[idx] = predictions[idx]
            return final_scores
        
        # Get all unique products from purchase history
        all_products = []
        for order_prods in orders_map.values():
            for product_id, _ in order_prods:
                all_products.append(product_id)
        
        product_to_idx = self._mappings.get('product_to_idx', {})
        
        # Calculate recency weights (newer orders get higher weights)
        # Recent orders: weight = 0.65, 0.50, 0.42, 0.35, 0.28, 0.20, ...
        max_history = min(len(sorted_orders), 15)
        
        # Weight formula: exponential decay from most recent
        # Most recent order gets weight 1.0, oldest gets much less
        recency_weights = {}
        
        for i, order_ts in enumerate(sorted_orders[-max_history:]):
            # Position from end (0 = most recent)
            position_from_end = max_history - 1 - i
            # Exponential decay: weight = 0.7 ^ position_from_end
            weight = 0.7 ** position_from_end
            recency_weights[order_ts] = weight
        
        # Normalize weights
        total_weight = sum(recency_weights.values())
        if total_weight > 0:
            for ts in recency_weights:
                recency_weights[ts] /= total_weight
        
        # Build product scores based on recency
        product_recency_scores = {}
        
        for order_ts, order_prods in orders_map.items():
            weight = recency_weights.get(order_ts, 0)
            
            for product_id, _ in order_prods:
                if product_id not in product_recency_scores:
                    product_recency_scores[product_id] = 0.0
                product_recency_scores[product_id] += weight
        
        # Combine model predictions with recency bias
        final_scores = {}
        
        for idx in range(2, len(predictions)):
            product_id = idx_to_product.get(idx)
            if not product_id:
                continue
            
            model_score = float(predictions[idx])
            recency_score = product_recency_scores.get(product_id, 0.0)
            
            # Fusion: weighted combination
            # More recency weight = more personalization
            # recency_boost factor (0.3) determines how much recency matters
            recency_boost = 0.35
            combined_score = (1 - recency_boost) * model_score + recency_boost * recency_score * 2.0
            
            # If product is in user's history, apply extra boost
            if product_id in all_products:
                # Find how recent (0 = very recent)
                for i, order_ts in enumerate(sorted_orders):
                    if product_id in [p for p, _ in orders_map[order_ts]]:
                        recent_factor = 0.7 ** (len(sorted_orders) - 1 - i)
                        combined_score += 0.15 * recent_factor
                        break
            
            if combined_score >= threshold * 0.5:
                final_scores[idx] = combined_score
        
        # If no products meet threshold, include top model predictions anyway
        if not final_scores:
            for idx in range(2, len(predictions)):
                final_scores[idx] = predictions[idx]
        
        return final_scores