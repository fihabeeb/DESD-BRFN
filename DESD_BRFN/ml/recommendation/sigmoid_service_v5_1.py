"""
Recommendation service for V5.1 LSTM + Attention model with recency boosting.

Key features:
- Uses V5.1 model (LSTM + dot-product attention)
- Input shape: (15 orders, 5 items) - sequence preserved
- Applies recency bias: more recent orders weighted higher
"""
import pickle
import numpy as np
import logging
from products.models import Product
from django.db import models

logger = logging.getLogger(__name__)


class LSTMServiceV5_1:
    """Service for V5.1 LSTM + Attention model."""
    
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
                model_path="ml/recommendation/final/sigmoid_v5_1.keras",
                mappings_path="ml/recommendation/final/sigmoid_v5_1_mappings.pkl"):
        """Load V5.1 model and mappings."""
        if self._model is not None:
            print("V5.1 model already loaded")
            return
            
        try:
            from tensorflow.keras.models import load_model
            
            self._model = load_model(model_path, compile=False, safe_mode=False)
            
            with open(mappings_path, 'rb') as f:
                self._mappings = pickle.load(f)
            
            print(f"V5.1 model loaded successfully!")
            logger.info(f"V5.1 model loaded: {self._mappings.get('num_products', '?')} products")
            
        except Exception as e:
            print(f"FAILED to load V5.1 model: {e}")
            logger.error(f"Failed to load V5.1 model: {e}")
            self._model = None
    
    # def get_recommendations(self, user_id, purchase_history_with_timestamps, top_k=5):
    #     """
    #     Get recommendations with recency boosting.
        
    #     Args:
    #         user_id: int
    #         purchase_history_with_timestamps: list of (product_id, datetime) tuples
    #         top_k: number of recommendations
            
    #     Returns:
    #         list of dict: [{'product': Product, 'score': float, 'confidence': str}, ...]
    #     """
    #     print(f"V5.1 get_recommendations called, model ready: {self._model is not None}")
        
    #     if not self._model:
    #         print("V5.1 model not loaded - returning popular")
    #         logger.warning("V5.1 model not loaded")
    #         return self._get_popular_recommendations(top_k)
        
    #     if not purchase_history_with_timestamps:
    #         print("No purchase history - returning popular")
    #         return self._get_popular_recommendations(top_k)
        
    #     print(f"User history length: {len(purchase_history_with_timestamps)}")
        
    #     try:
    #         mappings = self._mappings
    #         product_to_idx = mappings.get('p2i', mappings.get('product_to_idx', {}))
    #         idx_to_product = mappings.get('i2p', mappings.get('idx_to_product', {}))
    #         user_to_cluster = mappings.get('u2c', mappings.get('user_to_cluster', {}))
    #         max_order_history = 15
    #         max_items_per_order = 5
    #         other_token = 1
            
    #         print(f"p2i count: {len(product_to_idx)}, i2p count: {len(idx_to_product)}")
            
    #         orders_map = {}
    #         for product_id, timestamp in purchase_history_with_timestamps:
    #             order_key = timestamp
    #             if order_key not in orders_map:
    #                 orders_map[order_key] = []
    #             orders_map[order_key].append((product_id, timestamp))
            
    #         sorted_orders = sorted(orders_map.keys())
            
    #         context_products = []
    #         context_timestamps = []
            
    #         recent_orders = sorted_orders[-max_order_history:]
            
    #         for ts in recent_orders:
    #             order_prods = orders_map[ts]
    #             if order_prods and isinstance(order_prods[0], tuple):
    #                 prods_only = [p for p, _ in order_prods]
    #             else:
    #                 prods_only = list(order_prods)
                
    #             prods_only = prods_only[:max_items_per_order]
                
    #             if len(prods_only) < max_items_per_order:
    #                 prods_only = prods_only + [0] * (max_items_per_order - len(prods_only))
                
    #             encoded = [product_to_idx.get(p, other_token) if p != 0 else 0 for p in prods_only]
    #             context_products.append(encoded)
                
    #             context_timestamps.append(self._extract_temporal_features(ts))
            
    #         while len(context_products) < max_order_history:
    #             context_products = [[0] * max_items_per_order] + context_products
    #             context_timestamps = [[0.0] * 5] + context_timestamps

           
    #         # print(recent_orders)
            
    #         prod_input = np.array([context_products], dtype=np.int32)
    #         time_input = np.array([context_timestamps], dtype=np.float32)
            
    #         cluster_id = user_to_cluster.get(user_id, 0)
    #         user_cluster = np.array([[cluster_id]], dtype=np.int32)
            
    #         import tensorflow as tf
    #         logits, attention = self._model.predict(
    #             [prod_input, time_input, user_cluster],
    #             verbose=0
    #         )
            
    #         probs = tf.nn.softmax(logits, axis=-1).numpy()
    #         attn_weights = attention[0].tolist()
    #         print(f"Sum of weights: {sum(attn_weights):.6f}")
            
    #         print(f"Prediction: probs shape={probs.shape}, top 3 indices={probs[0].argsort()[-3:]}")
            
    #         final_scores = self._apply_recency_bias(
    #             purchase_history_with_timestamps,
    #             probs,
    #             idx_to_product
    #         )
            
    #         print(f"final_scores length: {len(final_scores)}, top 3: {list(sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)[:3])}")
            
    #         sorted_indices = sorted(final_scores.keys(), key=lambda x: final_scores[x], reverse=True)
            
    #         recommended = []
    #         seen_products = set()
            
    #         for idx in sorted_indices:
    #             if len(recommended) >= top_k:
    #                 break
                
    #             score = final_scores[idx]
    #             product_id = idx_to_product.get(idx)
                
    #             if not product_id or product_id in seen_products:
    #                 continue
                
    #             seen_products.add(product_id)
                
    #             try:
    #                 product = Product.objects.get(
    #                     id=product_id,
    #                     availability='available'
    #                 )
    #                 recommended.append({
    #                     'product': product,
    #                     'score': float(score),
    #                     'probability': float(score),
    #                     'rank': len(recommended) + 1,
    #                     'confidence': f"#{len(recommended) + 1}"
    #                 })
    #             except Product.DoesNotExist:
    #                 pass
            
    #         return recommended
            
    #     except Exception as e:
    #         logger.error(f"Error in V5.1 recommendation: {e}", exc_info=True)
    #         return []
    
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
        
        skip_not_in_idx = 0
        skip_no_product_id = 0
        skip_not_in_db = 0
        added = 0
        
        probs = model_probs[0]  # Get first row from batch
        
        for idx in range(2, len(probs)):
            if idx not in idx_to_product:
                skip_not_in_idx += 1
                continue
            
            product_id = idx_to_product.get(idx)
            if not product_id:
                skip_no_product_id += 1
                continue
            
            model_score = float(probs[idx])
            recency_score = product_recency.get(product_id, 0.0)
            
            recency_boost = 0.5
            
            if recency_score > 0:
                combined = (1 - recency_boost) * model_score + recency_boost * recency_score * 2
                
                for recent_pos in range(min(3, num_orders)):
                    recent_order = sorted_timestamps[-(recent_pos + 1)]
                    if product_id in orders_map[recent_order]:
                        combined += 0.1 * (0.7 ** recent_pos)
            else:
                combined = model_score
            
            final_scores[idx] = combined
            added += 1
        
        print(f"DEBUG recency: skipped-not-in-i2p={skip_not_in_idx}, skipped-no-product-id={skip_no_product_id}, added={added}")
        
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
    
    def get_attention_weights(self, user_id, purchase_history_with_timestamps):
        """
        Get attention weights for user's order history.
        
        Returns attention for each past order to understand what the model focuses on.
        
        Args:
            user_id: int
            purchase_history_with_timestamps: list of (product_id, datetime) tuples
            
        Returns:
            dict: {
                'attention_weights': [list of 15 weights],
                'order_details': [{'date': str, 'weight': float, 'products': [list]}, ...]
            }
        """
        if not self._model:
            logger.warning("V5.1 model not loaded")
            return None
        
        if not purchase_history_with_timestamps:
            return None
        
        try:
            mappings = self._mappings
            product_to_idx = mappings.get('p2i', {})
            user_to_cluster = mappings.get('u2c', {})
            
            orders_map = {}
            for product_id, timestamp in purchase_history_with_timestamps:
                order_key = timestamp
                if order_key not in orders_map:
                    orders_map[order_key] = []
                orders_map[order_key].append(product_id)
            
            sorted_orders = sorted(orders_map.keys())
            
            context_products = []
            context_timestamps = []
            
            recent_orders = sorted_orders[-15:]
            
            for ts in recent_orders:
                prods = orders_map[ts][:5]
                if len(prods) < 5:
                    prods = prods + [0] * (5 - len(prods))
                
                encoded = [product_to_idx.get(p, 1) if p != 0 else 0 for p in prods]
                context_products.append(encoded)
                context_timestamps.append(self._extract_temporal_features(ts))
            
            while len(context_products) < 15:
                context_products = [[0]*5] + context_products
                context_timestamps = [[0.0]*5] + context_timestamps
            
            import tensorflow as tf
            prod_input = np.array([context_products], dtype=np.int32)
            time_input = np.array([context_timestamps], dtype=np.float32)
            cluster_id = user_to_cluster.get(user_id, 0)
            user_cluster = np.array([[cluster_id]], dtype=np.int32)
            
            _, attention = self._model.predict(
                [prod_input, time_input, user_cluster],
                verbose=0
            )
            
            attn_weights = attention[0].tolist()
            
            order_details = []
            for i, ts in enumerate(recent_orders):
                order_details.append({
                    'date': ts.strftime('%Y-%m-%d') if hasattr(ts, 'strftime') else str(ts),
                    'weight': float(attn_weights[i]) if i < len(attn_weights) else 0.0,
                    'products': orders_map[ts]
                })
            
            return {
                'attention_weights': attn_weights,
                'order_details': order_details
            }
            
        except Exception as e:
            logger.error(f"Error extracting attention: {e}", exc_info=True)
            return None
    
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
    
    def get_predictions_with_explanation(self, user_id, top_k=5):
        """
        Unified method: Get recommendations + attention in one call.
        
        Returns dict:
            - recommendations: list of recommended products
            - attention_weights: list of 15 weights
            - order_details: list of {date, weight, products}
            - num_orders: number of orders in history
        """
        if not self._model:
            logger.warning("V5.1 model not loaded")
            return {
                'recommendations': [],
                'attention_weights': [],
                'order_details': [],
                'num_orders': 0
            }
        
        history = self.get_user_purchase_history(user_id)
        num_orders = len(history)
        # print(history) # used to verify seq was right.
        
        if num_orders < 2:
            return {
                'recommendations': [],
                'attention_weights': [],
                'order_details': [],
                'num_orders': num_orders
            }
        
        mappings = self._mappings
        product_to_idx = mappings.get('p2i', {})
        idx_to_product = mappings.get('i2p', {})
        user_to_cluster = mappings.get('u2c', {})
        
        max_order_history = 15
        max_items_per_order = 5
        
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
        logits, attention = self._model.predict(
            [prod_input, time_input, user_cluster],
            verbose=0
        )
        
        probs = tf.nn.softmax(logits, axis=-1).numpy()
        attn_weights = attention[0].tolist()
        
        purchase_history_for_recency = []
        for order_id in sorted_order_ids:
            for pid in history[order_id]['products']:
                purchase_history_for_recency.append((pid, history[order_id]['timestamp']))
        
        final_scores = self._apply_recency_bias(
            purchase_history_for_recency,
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
                product = Product.objects.get(id=product_id, availability='available')
                recommended.append({
                    'product': product,
                    'score': float(score),
                    'probability': float(score),
                    'rank': len(recommended) + 1,
                    'confidence': f"#{len(recommended) + 1}"
                })
            except Product.DoesNotExist:
                pass
        
        order_details = []
        for i, order_id in enumerate(sorted_order_ids[-max_order_history:]):
            order = history[order_id]
            order_details.append({
                'date': order['timestamp'].strftime('%Y-%m-%d'),
                'weight': float(attn_weights[i]) if i < len(attn_weights) else 0.0,
                'products': order['products']
            })
        
        return {
            'recommendations': recommended,
            'attention_weights': attn_weights,
            'order_details': order_details,
            'num_orders': num_orders
        }
    
    def get_product_saliency(self, user_id, target_product_id):
        """
        Compute gradient-based saliency for a target product prediction.
        """
        if not self._model:
            return []
        
        history = self.get_user_purchase_history(user_id)
        
        if len(history) < 2:
            return []
        
        mappings = self._mappings
        product_to_idx = mappings.get('p2i', {})
        idx_to_product = mappings.get('i2p', {})
        
        target_idx = int(product_to_idx.get(target_product_id, 0))
        if target_idx == 0:
            return []
        
        max_order_history = 15
        max_items_per_order = 5
        
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
        
        import tensorflow as tf
        
        # Convert to tensors
        prod_input = tf.constant([context_products], dtype=tf.int32)
        time_input = tf.constant([context_timestamps], dtype=tf.float32)
        
        # Get user cluster or use default
        user_to_cluster = mappings.get('u2c', {})
        cluster_id = user_to_cluster.get(user_id, 0)
        user_cluster = tf.constant([[cluster_id]], dtype=tf.int32)
        
        # Get the embedding layer weights to compute gradients
        # We'll compute gradients with respect to the input embeddings
        embedding_layer = self._model.get_layer('embedding')
        
        with tf.GradientTape() as tape:
            embeddings = embedding_layer(prod_input)
        
            # Watch the embeddings
            tape.watch(embeddings)

            # Forward pass
            logits, _ = self._model([prod_input, time_input, user_cluster], training=False)
            target_score = logits[0, target_idx]
        
        # Compute gradients with respect to embedding weights
        grads = tape.gradient(target_score, embedding_layer.weights[0])
        
        if grads is None:
            # Fallback: compute saliency from logits directly
            return self._get_saliency_fallback(context_products, idx_to_product, target_idx)
        
        # Get saliency for each product in the input sequence
        saliency_map = tf.abs(grads).numpy()
        
        # Map saliency to actual product IDs
        product_scores = {}
        for order_idx in range(max_order_history):
            for item_idx in range(max_items_per_order):
                product_idx = context_products[order_idx][item_idx]
                if product_idx > 0 and product_idx < len(idx_to_product):
                    actual_pid = idx_to_product.get(int(product_idx))
                    if actual_pid and product_idx < len(saliency_map):
                        # Sum saliency across embedding dimensions
                        score = float(np.mean(saliency_map[product_idx]))
                        product_scores[actual_pid] = product_scores.get(actual_pid, 0) + score
        
        sorted_prods = sorted(product_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        
        result = []
        for pid, score in sorted_prods:
            try:
                product = Product.objects.get(id=pid)
                result.append({
                    'product_id': pid,
                    'product_name': product.name,
                    'saliency': float(score),
                })
            except Product.DoesNotExist:
                pass
        
        return result

    def _get_saliency_fallback(self, context_products, idx_to_product, target_idx):
        """
        Fallback method when gradient computation fails.
        Uses attention weights as a proxy for saliency.
        """
        product_scores = {}
        
        # Count product occurrences and weight by position (more recent = higher weight)
        for order_idx, order in enumerate(context_products):
            position_weight = 1.0 + (order_idx / len(context_products))  # Recent orders get higher weight
            for product_idx in order:
                if product_idx > 0 and product_idx < len(idx_to_product):
                    actual_pid = idx_to_product.get(int(product_idx))
                    if actual_pid:
                        product_scores[actual_pid] = product_scores.get(actual_pid, 0) + position_weight
        
        # Normalize scores
        if product_scores:
            max_score = max(product_scores.values())
            for pid in product_scores:
                product_scores[pid] = product_scores[pid] / max_score
        
        sorted_prods = sorted(product_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        
        result = []
        for pid, score in sorted_prods:
            try:
                product = Product.objects.get(id=pid)
                result.append({
                    'product_id': pid,
                    'product_name': product.name,
                    'saliency': float(score),
                })
            except Product.DoesNotExist:
                pass
        
        return result