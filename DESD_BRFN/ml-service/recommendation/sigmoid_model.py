"""Inference-only helpers extracted from the training module."""
import datetime
import numpy as np


def extract_temporal_features(timestamp: datetime.datetime):
    day_of_week = timestamp.weekday()
    day_sin = np.sin(2 * np.pi * day_of_week / 7.0)
    day_cos = np.cos(2 * np.pi * day_of_week / 7.0)
    month = timestamp.month
    month_sin = np.sin(2 * np.pi * month / 12.0)
    month_cos = np.cos(2 * np.pi * month / 12.0)
    is_weekend = 1.0 if day_of_week >= 5 else 0.0
    return [day_sin, day_cos, month_sin, month_cos, is_weekend]


def recommend_next_items_sigmoid(
    user_id,
    user_history_products,
    user_history_timestamps,
    model,
    product_to_idx,
    idx_to_product,
    user_to_idx,
    max_seq_len=7,
    top_k=5,
    other_token=1,
    normalize=True,
):
    """Return list of (product_id, probability) for the top-k products."""
    if len(user_history_products) > max_seq_len:
        user_history_products = user_history_products[-max_seq_len:]
        user_history_timestamps = user_history_timestamps[-max_seq_len:]

    pad_len = max_seq_len - len(user_history_products)
    if pad_len > 0:
        user_history_products = [0] * pad_len + user_history_products
        zero_feat = [0.0] * 5
        user_history_timestamps = [zero_feat] * pad_len + user_history_timestamps

    encoded_prods = []
    for p in user_history_products:
        if p == 0:
            encoded_prods.append(0)
        else:
            encoded_prods.append(product_to_idx.get(p, other_token))

    time_feats = [
        extract_temporal_features(ts) if isinstance(ts, datetime.datetime) else ts
        for ts in user_history_timestamps
    ]

    prod_input = np.array([encoded_prods], dtype=np.int32)
    time_input = np.array([time_feats], dtype=np.float32)
    user_enc = user_to_idx.get(user_id, 0)
    user_input = np.array([[user_enc]], dtype=np.int32)

    predictions = model.predict([prod_input, time_input, user_input], verbose=0)[0]

    valid_indices = [
        i for i in range(len(predictions))
        if i not in (0, other_token) and i in idx_to_product
    ]
    top_indices = sorted(valid_indices, key=lambda i: predictions[i], reverse=True)[:top_k]

    raw_scores = [float(predictions[i]) for i in top_indices]
    if normalize and raw_scores and sum(raw_scores) > 0:
        total = sum(raw_scores)
        scores = [s / total for s in raw_scores]
    else:
        scores = raw_scores

    return [(idx_to_product[i], scores[idx]) for idx, i in enumerate(top_indices)]
