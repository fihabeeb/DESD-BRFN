import os
import pickle
import datetime
import logging

import numpy as np

logger = logging.getLogger(__name__)

V5_1_MODEL_PATH = os.environ.get("V5_1_MODEL_PATH", "ml/recommendation/final/sigmoid_v5_1.keras")
V5_1_MAPPINGS_PATH = os.environ.get("V5_1_MAPPINGS_PATH", "ml/recommendation/final/sigmoid_v5_1_mappings.pkl")


class LSTMServiceV5_1:
    def __init__(self):
        self._model = None
        self._mappings = None

    def is_loaded(self) -> bool:
        return self._model is not None

    def load_model(self, model_path=V5_1_MODEL_PATH, mappings_path=V5_1_MAPPINGS_PATH):
        if self._model is not None:
            return
        try:
            from tensorflow.keras.models import load_model
            self._model = load_model(model_path, compile=False, safe_mode=False)
            with open(mappings_path, "rb") as f:
                self._mappings = pickle.load(f)
            logger.info("V5.1 model loaded: %s products", self._mappings.get("num_products", "?"))
        except Exception as e:
            logger.error("Failed to load V5.1 model: %s", e)
            self._model = None

    def _parse_ts(self, ts):
        if isinstance(ts, str):
            return datetime.datetime.fromisoformat(ts)
        return ts

    def _extract_temporal_features(self, ts):
        ts = self._parse_ts(ts)
        dow = ts.weekday()
        month = ts.month
        return [
            np.sin(2 * np.pi * dow / 7.0),
            np.cos(2 * np.pi * dow / 7.0),
            np.sin(2 * np.pi * month / 12.0),
            np.cos(2 * np.pi * month / 12.0),
            1.0 if dow >= 5 else 0.0,
        ]

    def _group_by_order(self, purchase_history):
        """Group flat [{product_id, timestamp}] list into {timestamp: [product_ids]}."""
        orders_map = {}
        for item in purchase_history:
            ts = self._parse_ts(item["timestamp"])
            if ts not in orders_map:
                orders_map[ts] = []
            orders_map[ts].append(item["product_id"])
        return orders_map

    def _build_inputs(self, orders_map):
        MAX_ORDERS = 15
        MAX_ITEMS = 5
        product_to_idx = self._mappings.get("p2i", {})

        sorted_ts = sorted(orders_map.keys())
        context_products = []
        context_timestamps = []

        for ts in sorted_ts[-MAX_ORDERS:]:
            prods = orders_map[ts][:MAX_ITEMS]
            if len(prods) < MAX_ITEMS:
                prods = prods + [0] * (MAX_ITEMS - len(prods))
            context_products.append([product_to_idx.get(p, 1) if p != 0 else 0 for p in prods])
            context_timestamps.append(self._extract_temporal_features(ts))

        while len(context_products) < MAX_ORDERS:
            context_products = [[0] * MAX_ITEMS] + context_products
            context_timestamps = [[0.0] * 5] + context_timestamps

        return context_products, context_timestamps, sorted_ts

    def _apply_recency_bias(self, orders_map, probs, idx_to_product):
        sorted_ts = sorted(orders_map.keys())
        num_orders = len(sorted_ts)

        product_recency = {}
        for pos_from_end, ts in enumerate(reversed(sorted_ts)):
            weight = 0.7 ** pos_from_end
            for pid in orders_map[ts]:
                product_recency[pid] = product_recency.get(pid, 0.0) + weight

        total = sum(product_recency.values())
        if total > 0:
            for pid in product_recency:
                product_recency[pid] /= total

        final_scores = {}
        row = probs[0]
        for idx in range(2, len(row)):
            product_id = idx_to_product.get(idx)
            if not product_id:
                continue
            model_score = float(row[idx])
            recency_score = product_recency.get(product_id, 0.0)
            if recency_score > 0:
                combined = 0.5 * model_score + 0.5 * recency_score * 2
                for recent_pos in range(min(3, num_orders)):
                    recent_ts = sorted_ts[-(recent_pos + 1)]
                    if product_id in orders_map[recent_ts]:
                        combined += 0.1 * (0.7 ** recent_pos)
            else:
                combined = model_score
            final_scores[idx] = combined

        return final_scores

    def get_predictions_with_explanation(self, user_id, purchase_history, top_k=5):
        """
        Args:
            user_id: int
            purchase_history: list of {"product_id": int, "timestamp": str (ISO)}
            top_k: int
        Returns:
            {"recommendations": [...], "attention_weights": [...], "order_details": [...], "num_orders": int}
            Each recommendation: {"product_id": int, "score": float, "rank": int}
        """
        import tensorflow as tf

        empty = {"recommendations": [], "attention_weights": [], "order_details": [], "num_orders": 0}
        if not self._model or not purchase_history:
            return empty

        orders_map = self._group_by_order(purchase_history)
        num_orders = len(orders_map)
        if num_orders < 2:
            return {**empty, "num_orders": num_orders}

        idx_to_product = self._mappings.get("i2p", {})
        user_to_cluster = self._mappings.get("u2c", {})

        context_products, context_timestamps, sorted_ts = self._build_inputs(orders_map)

        prod_input = np.array([context_products], dtype=np.int32)
        time_input = np.array([context_timestamps], dtype=np.float32)
        cluster_id = user_to_cluster.get(user_id, 0)
        user_cluster = np.array([[cluster_id]], dtype=np.int32)

        logits, attention = self._model.predict([prod_input, time_input, user_cluster], verbose=0)
        probs = tf.nn.softmax(logits, axis=-1).numpy()
        attn_weights = attention[0].tolist()

        final_scores = self._apply_recency_bias(orders_map, probs, idx_to_product)
        sorted_indices = sorted(final_scores, key=lambda x: final_scores[x], reverse=True)

        recommended = []
        seen = set()
        for idx in sorted_indices:
            if len(recommended) >= top_k:
                break
            product_id = idx_to_product.get(idx)
            if not product_id or product_id in seen:
                continue
            seen.add(product_id)
            recommended.append({
                "product_id": product_id,
                "score": float(final_scores[idx]),
                "rank": len(recommended) + 1,
            })

        recent_ts = sorted_ts[-15:]
        order_details = sorted(
            [
                {
                    "date": ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts),
                    "weight": float(attn_weights[i]) if i < len(attn_weights) else 0.0,
                    "products": orders_map[ts],
                }
                for i, ts in enumerate(recent_ts)
            ],
            key=lambda x: x["date"],
            reverse=True,
        )

        return {
            "recommendations": recommended,
            "attention_weights": attn_weights,
            "order_details": order_details,
            "num_orders": num_orders,
        }

    def get_product_saliency(self, user_id, target_product_id, purchase_history):
        """
        Args:
            user_id: int
            target_product_id: int
            purchase_history: list of {"product_id": int, "timestamp": str (ISO)}
        Returns:
            list of {"product_id": int, "saliency": float}
        """
        import tensorflow as tf

        if not self._model or not purchase_history:
            return []

        mappings = self._mappings
        product_to_idx = mappings.get("p2i", {})
        idx_to_product = mappings.get("i2p", {})
        user_to_cluster = mappings.get("u2c", {})

        target_idx = int(product_to_idx.get(target_product_id, 0))
        if target_idx == 0:
            return []

        orders_map = self._group_by_order(purchase_history)
        context_products, context_timestamps, _ = self._build_inputs(orders_map)

        prod_input = tf.constant([context_products], dtype=tf.int32)
        time_input = tf.constant([context_timestamps], dtype=tf.float32)
        cluster_id = user_to_cluster.get(user_id, 0)
        user_cluster = tf.constant([[cluster_id]], dtype=tf.int32)

        try:
            embedding_layer = self._model.get_layer("embedding")
            with tf.GradientTape() as tape:
                embedding_layer(prod_input)
                tape.watch(embedding_layer.weights[0])
                logits, _ = self._model([prod_input, time_input, user_cluster], training=False)
                target_score = logits[0, target_idx]

            grads = tape.gradient(target_score, embedding_layer.weights[0])
            if grads is None:
                return self._saliency_fallback(context_products, idx_to_product)

            saliency_map = tf.abs(grads).numpy()
            product_scores = {}
            MAX_ORDERS, MAX_ITEMS = 15, 5
            for oi in range(MAX_ORDERS):
                for ii in range(MAX_ITEMS):
                    pidx = context_products[oi][ii]
                    if pidx > 0 and pidx < len(saliency_map):
                        actual_pid = idx_to_product.get(int(pidx))
                        if actual_pid:
                            product_scores[actual_pid] = (
                                product_scores.get(actual_pid, 0) + float(np.mean(saliency_map[pidx]))
                            )
        except Exception as e:
            logger.error("Saliency computation failed: %s", e)
            return self._saliency_fallback(context_products, idx_to_product)

        sorted_prods = sorted(product_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        return [{"product_id": pid, "saliency": float(score)} for pid, score in sorted_prods]

    def _saliency_fallback(self, context_products, idx_to_product):
        product_scores = {}
        for oi, order in enumerate(context_products):
            weight = 1.0 + (oi / len(context_products))
            for pidx in order:
                if pidx > 0:
                    actual_pid = idx_to_product.get(int(pidx))
                    if actual_pid:
                        product_scores[actual_pid] = product_scores.get(actual_pid, 0) + weight
        if product_scores:
            max_score = max(product_scores.values())
            product_scores = {pid: s / max_score for pid, s in product_scores.items()}
        sorted_prods = sorted(product_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        return [{"product_id": pid, "saliency": float(score)} for pid, score in sorted_prods]
