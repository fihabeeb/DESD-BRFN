import numpy as np
import tensorflow as tf
from tensorflow import keras
from collections import defaultdict, Counter
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.sequence import pad_sequences
import pickle
import datetime
import logging

logger = logging.getLogger(__name__)

from orders.models import OrderItem, OrderPayment
from django.db.models import Sum, Count, Avg

# ------------------------------------------------------------
#  Helper: extract temporal features
# ------------------------------------------------------------
def extract_temporal_features(timestamp: datetime.datetime):
    day_of_week = timestamp.weekday()
    day_sin = np.sin(2 * np.pi * day_of_week / 7.0)
    day_cos = np.cos(2 * np.pi * day_of_week / 7.0)
    month = timestamp.month
    month_sin = np.sin(2 * np.pi * month / 12.0)
    month_cos = np.cos(2 * np.pi * month / 12.0)
    is_weekend = 1.0 if day_of_week >= 5 else 0.0
    return [day_sin, day_cos, month_sin, month_cos, is_weekend]

# ------------------------------------------------------------
#  Data extraction from DB (with order grouping)
# ------------------------------------------------------------
def get_user_orders_with_products():
    user_orders = defaultdict(list)
    order_items = OrderItem.objects.filter(
        producer_order__payment__payment_status='paid'
    ).exclude(
        producer_order__payment__user__customer_profile__id=1
    ).select_related(
        'product', 'producer_order__payment__user'
    ).order_by('producer_order__payment__created_at')

    current_user = None
    current_order = None
    products_in_order = []

    for item in order_items:
        user = item.producer_order.payment.user
        order_id = item.producer_order.payment.id
        timestamp = item.producer_order.payment.created_at
        product_id = item.product.id

        if user is None:
            continue

        if current_user != user.id:
            current_user = user.id
            current_order = None
            products_in_order = []

        if current_order != order_id:
            if current_order is not None and products_in_order:
                user_orders[current_user].append((current_order, timestamp, list(set(products_in_order))))
            current_order = order_id
            products_in_order = [product_id]
        else:
            if product_id not in products_in_order:
                products_in_order.append(product_id)

    if current_user and current_order and products_in_order:
        user_orders[current_user].append((current_order, timestamp, products_in_order))

    return dict(user_orders)

# ------------------------------------------------------------
#  Limit to top K products (most frequent in all orders)
# ------------------------------------------------------------
def get_top_products(user_orders, top_k=100):
    product_counter = Counter()
    for orders in user_orders.values():
        for _, _, prods in orders:
            product_counter.update(prods)
    top_product_ids = [pid for pid, _ in product_counter.most_common(top_k)]
    return set(top_product_ids)

# ------------------------------------------------------------
#  Encode products
# ------------------------------------------------------------
def encode_products_limited(all_product_ids, top_product_set):
    """
    Maps product IDs that are in top_product_set to 1..N.
    All others (rare products) are mapped to a single "other" token
    padding=0, other=1, then products start at 2.
    """
    # Create mapping for top products
    top_list = sorted(top_product_set)  # deterministic order
    product_to_idx = {pid: i+2 for i, pid in enumerate(top_list)}  # start at 2
    # Reserve 0 for padding, 1 for "other"
    product_to_idx[0] = 0  # padding
    # "other" token id = 1
    other_token = 1
    idx_to_product = {0: 0, other_token: None}  # None means other
    for pid, idx in product_to_idx.items():
        if pid != 0:
            idx_to_product[idx] = pid
    num_products = len(top_list) + 1  # +1 for "other" token (index 1)
    return product_to_idx, idx_to_product, num_products, other_token

# ------------------------------------------------------------
#  Build sequences with limited product vocabulary
# ------------------------------------------------------------
def build_sequences_limited(user_orders, product_to_idx, other_token, max_seq_len=7):
    X_products = []
    X_time = []
    y_multi_hot = []
    user_ids = []
    num_classes = max(product_to_idx.values()) + 1  # includes padding and other

    for user_id, orders in user_orders.items():
        if len(orders) < 2:
            continue

        for i in range(len(orders) - 1):
            context_orders = orders[:i+1]
            target_order = orders[i+1]

            # Build context product sequence (flattened)
            context_products = []
            context_timestamps = []
            for (_, ts, prod_list) in context_orders:
                for p in prod_list:
                    context_products.append(p)
                    context_timestamps.append(ts)

            # Truncate/pad to max_seq_len
            if len(context_products) > max_seq_len:
                context_products = context_products[-max_seq_len:]
                context_timestamps = context_timestamps[-max_seq_len:]
            pad_len = max_seq_len - len(context_products)
            if pad_len > 0:
                context_products = [0] * pad_len + context_products
                zero_feat = [0.0] * 5
                context_timestamps = [zero_feat] * pad_len + context_timestamps

            # Encode products (map rare ones to other_token)
            encoded_prods = []
            for p in context_products:
                if p == 0:
                    encoded_prods.append(0)
                else:
                    encoded_prods.append(product_to_idx.get(p, other_token))

            # Time features
            time_feats = [extract_temporal_features(ts) if isinstance(ts, datetime.datetime) else ts
                          for ts in context_timestamps]

            # Multi-hot target for next order (only top products + other)
            target_vector = [0] * num_classes
            for target_pid in target_order[2]:
                idx = product_to_idx.get(target_pid, other_token)
                target_vector[idx] = 1

            X_products.append(encoded_prods)
            X_time.append(time_feats)
            y_multi_hot.append(target_vector)
            user_ids.append(user_id)

    return (np.array(X_products, dtype=np.int32),
            np.array(X_time, dtype=np.float32),
            np.array(y_multi_hot, dtype=np.float32),
            user_ids)

# ------------------------------------------------------------
#  Encode users
# ------------------------------------------------------------
def encode_users(user_ids):
    unique = sorted(set(user_ids))
    user_to_idx = {uid: i+1 for i, uid in enumerate(unique)}
    idx_to_user = {i+1: uid for i, uid in enumerate(unique)}
    user_to_idx[0] = 0
    idx_to_user[0] = 0
    return user_to_idx, idx_to_user, len(unique) + 1

# ------------------------------------------------------------
#  Training function
# ------------------------------------------------------------
def train_sigmoid_lstm(
    max_seq_len=8,
    batch_size=32,
    epochs=25,
    test_size=0.2,
    top_k_products=200,
    save_model=True,
    model_save_path="ml/recommendation/final/sigmoid_lstm.keras",
    mappings_save_path="ml/recommendation/final/sigmoid_mappings.pkl"
):
    """
    Returns: (model, product_to_idx, idx_to_product, user_to_idx, idx_to_user, history)
    """
    print("=" * 60)
    print("Training sigmoid LSTM (multi-label, top-K products)")
    print("=" * 60)

    # 1. Load orders
    print("\n[1/6] Loading user orders...")
    user_orders = get_user_orders_with_products()
    if not user_orders:
        raise ValueError("No user orders found.")

    # 2. Limit to top K products
    print(f"\n[2/6] Selecting top {top_k_products} most frequent products...")
    top_products = get_top_products(user_orders, top_k=top_k_products)
    print(f"Selected {len(top_products)} products (plus 'other' token)")

    # 3. Encode products
    product_to_idx, idx_to_product, num_classes, other_token = encode_products_limited(
        [], (top_products)
    )
    print(f"Number of output classes (including 'other'): {num_classes}")

    # 4. Build sequences
    print("\n[3/6] Building sequences...")
    X_prod, X_time, y_multi, user_ids = build_sequences_limited(
        user_orders, product_to_idx, other_token, max_seq_len
    )
    print(f"Total samples: {len(X_prod)}")
    print(f"Positive labels per sample: {np.sum(y_multi, axis=1).mean():.2f}")

    # 5. Encode users
    user_to_idx, idx_to_user, num_users = encode_users(user_ids)
    user_encoded = np.array([user_to_idx[uid] for uid in user_ids], dtype=np.int32).reshape(-1, 1)

    # 6. Train/val split
    print("\n[4/6] Splitting data...")
    indices = np.arange(len(X_prod))
    train_idx, val_idx = train_test_split(indices, test_size=test_size, random_state=42)

    X_prod_train = X_prod[train_idx]
    X_prod_val   = X_prod[val_idx]
    X_time_train = X_time[train_idx]
    X_time_val   = X_time[val_idx]
    y_train = y_multi[train_idx]
    y_val   = y_multi[val_idx]
    user_train = user_encoded[train_idx]
    user_val   = user_encoded[val_idx]

    # Compute class weights to balance positive/negative
    # For multi-label, we can use simple pos_weight per class or global pos_weight.
    # Here we compute a global positive weight (neg/pos ratio)
    pos_count = np.sum(y_train)
    neg_count = y_train.size - pos_count
    pos_weight = neg_count / max(pos_count, 1)
    print(f"Positive weight: {pos_weight:.2f}")

    # 7. Build model
    print("\n[5/6] Building LSTM model...")
    product_input = keras.Input(shape=(max_seq_len,), name='product_input')
    time_input = keras.Input(shape=(max_seq_len, 5), name='time_input')
    user_input = keras.Input(shape=(1,), name='user_input')

    prod_embed = keras.layers.Embedding(
        input_dim=num_classes + 1,  # +1 because indices go up to num_classes (including other)
        output_dim=64,
        mask_zero=True,
        name='prod_emb'
    )(product_input)

    combined = keras.layers.Concatenate(axis=-1)([prod_embed, time_input])
    lstm_out = keras.layers.LSTM(64, dropout=0.2, return_sequences=False, name='lstm')(combined)

    user_embed = keras.layers.Embedding(input_dim=num_users, output_dim=16, name='user_emb')(user_input)
    user_flat = keras.layers.Flatten()(user_embed)

    merged = keras.layers.Concatenate()([lstm_out, user_flat])
    dense = keras.layers.Dense(32, activation='relu')(merged)
    # dense = keras.layers.BatchNormalization()(dense)
    dropout = keras.layers.Dropout(0.2)(dense)

    # Sigmoid output for multi-label
    output_size = max(product_to_idx.values()) + 1
    output = keras.layers.Dense(output_size, activation='sigmoid', name='output')(dropout)

    model = keras.Model(inputs=[product_input, time_input, user_input], outputs=output)

    # Use binary crossentropy with class weight (apply via sample weights or inside loss)
    # We'll add a custom loss that applies pos_weight
    
    model.compile(
        optimizer='adam',
        # loss='binary_crossentropy',
        loss=tf.keras.losses.BinaryFocalCrossentropy(),
        # loss=weighted_binary_crossentropy(weight),
        metrics=['binary_accuracy', tf.keras.metrics.Precision(top_k=5), tf.keras.metrics.Recall(top_k=5)]
    )
    model.summary()

    callbacks = [
        keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True, verbose=1),
        keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, verbose=1),
        keras.callbacks.ModelCheckpoint('ml/recommendation/final/checkpoint/sigmoid_checkpoint.keras', monitor='val_loss', save_best_only=True)
    ]

    # 8. Train
    print("\n[6/6] Training...")
    history = model.fit(
        [X_prod_train, X_time_train, user_train],
        y_train,
        batch_size=batch_size,
        epochs=epochs,
        validation_data=([X_prod_val, X_time_val, user_val], y_val),
        callbacks=callbacks,
        verbose=1
    )

    # Evaluate
    val_loss, val_bin_acc, val_prec, val_rec= model.evaluate([X_prod_val, X_time_val, user_val], y_val, verbose=0)
    print(f"\nValidation: loss={val_loss:.4f}, binary_accuracy={val_bin_acc:.4f}, precision={val_prec:.4f}, recall={val_rec:.4f}")

    # -------------
    # Multi-label ranking metrics
    from sklearn.metrics import average_precision_score, label_ranking_average_precision_score

    y_pred_proba = model.predict([X_prod_val, X_time_val, user_val], verbose=0)
    # 1. Mean Average Precision (per-class)
    ap_list = []
    for i in range(y_val.shape[1]):
        if len(np.unique(y_val[:, i])) > 1:
            ap_list.append(average_precision_score(y_val[:, i], y_pred_proba[:, i]))
    map_score = np.mean(ap_list) if ap_list else 0.0

    # 2. Label Ranking Average Precision
    lrap_score = label_ranking_average_precision_score(y_val, y_pred_proba)
    print(f"Mean AP (per-class): {map_score:.4f}")
    print(f"Label Ranking AP: {lrap_score:.4f}")
    # ------------


    # Save
    if save_model:
        print(f"Saving model to {model_save_path}")
        model.save(model_save_path)
        mappings = {
            'product_to_idx': product_to_idx,
            'idx_to_product': idx_to_product,
            'user_to_idx': user_to_idx,
            'idx_to_user': idx_to_user,
            'max_seq_len': max_seq_len,
            'num_products': num_classes,
            'num_users': num_users,
            'other_token': other_token,
            'top_k_products': top_k_products
        }
        with open(mappings_save_path, 'wb') as f:
            pickle.dump(mappings, f)
        print("Mappings saved.")

    # Return exactly 6 values
    return model, product_to_idx, idx_to_product, user_to_idx, idx_to_user, history

# ------------------------------------------------------------
#  Recommendation function
# ------------------------------------------------------------
def recommend_next_items_sigmoid(
    user_id, user_history_products, user_history_timestamps,
    model, product_to_idx, idx_to_product, user_to_idx,
    max_seq_len=7, top_k=5, other_token=1, normalize=True,
):
    """
    Returns list of (product_id, probability) for top-k products.
    Skips 'other' token (index 1) and padding (0).
    """
    # Process history
    if len(user_history_products) > max_seq_len:
        user_history_products = user_history_products[-max_seq_len:]
        user_history_timestamps = user_history_timestamps[-max_seq_len:]
    pad_len = max_seq_len - len(user_history_products)
    if pad_len > 0:
        user_history_products = [0] * pad_len + user_history_products
        zero_feat = [0.0] * 5
        user_history_timestamps = [zero_feat] * pad_len + user_history_timestamps

    # Encode (map rare products to other_token)
    encoded_prods = []
    for p in user_history_products:
        if p == 0:
            encoded_prods.append(0)
        else:
            encoded_prods.append(product_to_idx.get(p, other_token))

    time_feats = [extract_temporal_features(ts) if isinstance(ts, datetime.datetime) else ts
                  for ts in user_history_timestamps]

    prod_input = np.array([encoded_prods], dtype=np.int32)
    time_input = np.array([time_feats], dtype=np.float32)
    user_enc = user_to_idx.get(user_id, 0)
    user_input = np.array([[user_enc]], dtype=np.int32)

    predictions = model.predict([prod_input, time_input, user_input], verbose=0)[0]

    # Get top-k indices (skip 0 and other_token)
    valid_indices = [i for i in range(len(predictions)) if i not in (0, other_token) and i in idx_to_product]
    top_indices = sorted(valid_indices, key=lambda i: predictions[i], reverse=True)[:top_k]

    # Extract raw scores
    raw_scores = [float(predictions[i]) for i in top_indices]

    # Normalize to sum = 1.0 (if desired and if there is at least one positive score)
    if normalize and raw_scores and sum(raw_scores) > 0:
        total = sum(raw_scores)
        normalized_scores = [s / total for s in raw_scores]
    else:
        normalized_scores = raw_scores  # fallback to raw

    # Return list of (product_id, normalized_score)
    return [(idx_to_product[i], normalized_scores[idx]) for idx, i in enumerate(top_indices)]

