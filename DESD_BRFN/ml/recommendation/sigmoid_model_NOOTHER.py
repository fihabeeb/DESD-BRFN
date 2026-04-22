import numpy as np
import tensorflow as tf
from tensorflow import keras
from collections import defaultdict, Counter
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.sequence import pad_sequences
import pickle
import datetime
import logging

from django.db.models import Window, F
from django.db.models.functions import RowNumber

logger = logging.getLogger(__name__)

from orders.models import OrderItem, OrderPayment
from django.db.models import Sum, Count, Avg

# ------------------------------------------------------------
#  Helper: extract temporal features
# ------------------------------------------------------------
def extract_temporal_features(timestamp: datetime.datetime, ref_timestamp=None):
    """
    Returns a single scalar: normalized days since ref_timestamp.
    If ref_timestamp is None, returns 0.0 (will be set later during sequence building).
    """
    if ref_timestamp is None:
        return 0.0
    delta = (timestamp - ref_timestamp).total_seconds() / (24 * 3600.0)
    # Normalize by a reasonable max (e.g., 365 days) – clip to [0,1]
    max_days = 365.0
    return min(delta / max_days, 1.0)

# ------------------------------------------------------------
#  Data extraction from DB (with order grouping)
# ------------------------------------------------------------
def get_user_orders_with_products():
    '''
    quantity ignored.
    user_id : (order_num, datetime, products in order)
    1 : (664, datetime.datetime(2026, 3, 14, 10, 12, 53, 931192, tzinfo=datetime.timezone.utc), [42, 43, 140, 271, 52, 183, 184])]
    '''
    user_orders = defaultdict(list)
    # order_items = OrderItem.objects.filter(
    #     producer_order__payment__payment_status='paid'
    # ).exclude(
    #     producer_order__payment__user__customer_profile__id=1
    # ).select_related(
    #     'product', 'producer_order__payment__user'
    # ).order_by('producer_order__payment__created_at')

    order_items = OrderItem.objects.filter(
        producer_order__payment__payment_status='paid'
    ).exclude(
        producer_order__payment__user__customer_profile__id=1
    ).select_related(
        'product', 'producer_order__payment__user'
    ).order_by('-producer_order__payment__created_at')

    # order_items = OrderItem.objects.filter(
    #     producer_order__payment__payment_status='paid'
    # ).exclude(
    #     producer_order__payment__user__customer_profile__id=1
    # ).annotate(
    #     rn=Window(
    #         expression=RowNumber(),
    #         partition_by=[F('producer_order__payment__user')],
    #         order_by=F('producer_order__payment__created_at').desc()
    #     )
    # ).filter(
    #     rn__gt=1  # Exclude the first row (latest) for each user
    # ).select_related(
    #     'product', 'producer_order__payment__user'
    # ).order_by('producer_order__payment__created_at')

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
    All other (rare) products are mapped to 0 (padding).
    padding=0, real products start at 1.
    """
    top_list = sorted(top_product_set)  # deterministic order
    product_to_idx = {pid: i+1 for i, pid in enumerate(top_list)}  # start at 1
    product_to_idx[0] = 0  # padding
    idx_to_product = {0: 0}
    for pid, idx in product_to_idx.items():
        if pid != 0:
            idx_to_product[idx] = pid
    num_products = len(top_list) + 1  # +1 for padding (index 0)
    # No separate "other" token
    other_token = None
    return product_to_idx, idx_to_product, num_products, other_token

# ------------------------------------------------------------
#  Build sequences with limited product vocabulary
# ------------------------------------------------------------
def build_sequences_limited(user_orders, product_to_idx, other_token, max_seq_len=7):
    """
    other_token is ignored (None). Rare products map to 0.
    Time features: single scalar (normalized days since first product in sequence).
    """
    X_products = []
    X_time = []
    y_multi_hot = []
    user_ids = []
    num_classes = max(product_to_idx.values()) + 1  # includes padding (0)

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

            # Determine reference timestamp (oldest in the truncated sequence)
            if context_timestamps:
                ref_ts = min(context_timestamps)
            else:
                ref_ts = None

            pad_len = max_seq_len - len(context_products)
            if pad_len > 0:
                context_products = [0] * pad_len + context_products
                # For padding, time feature = 0.0
                context_timestamps = [0.0] * pad_len + context_timestamps

            # Encode products: rare -> 0 (padding)
            encoded_prods = []
            for p in context_products:
                if p == 0:
                    encoded_prods.append(0)
                else:
                    encoded_prods.append(product_to_idx.get(p, 0))

            # Single time feature: normalized days since ref_ts
            time_feats = []
            for ts in context_timestamps:
                if ts == 0.0 or ref_ts is None:
                    time_feats.append(0.0)
                else:
                    time_feats.append(extract_temporal_features(ts, ref_ts))

            # Multi-hot target for next order – only top products (rare -> 0, we skip)
            target_vector = [0] * num_classes
            valid_target = False
            for target_pid in target_order[2]:
                idx = product_to_idx.get(target_pid, 0)
                if idx != 0:
                    target_vector[idx] = 1
                    valid_target = True
            if not valid_target:
                # Skip samples where all target products are rare (would predict 0)
                continue

            X_products.append(encoded_prods)
            X_time.append(time_feats)          # shape: (max_seq_len,)
            y_multi_hot.append(target_vector)
            user_ids.append(user_id)

    # Convert to numpy arrays
    X_products_array = np.array(X_products, dtype=np.int32)                # (n, max_seq_len)
    X_time_array = np.array(X_time, dtype=np.float32).reshape(-1, max_seq_len, 1)  # (n, max_seq_len, 1)
    y_multi_array = np.array(y_multi_hot, dtype=np.float32)
    return X_products_array, X_time_array, y_multi_array, user_ids

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
    max_seq_len=5,
    batch_size=32,
    epochs=25,
    test_size=0.2,
    top_k_products=164,
    save_model=True,
    model_save_path="ml/recommendation/final/sigmoid_lstm.keras",
    mappings_save_path="ml/recommendation/final/sigmoid_mappings.pkl"
):
    print("=" * 60)
    print("Training sigmoid LSTM (multi-label, top-K products, no 'other' token)")
    print("=" * 60)

    # 1. Load orders
    print("\n[1/6] Loading user orders...")
    user_orders = get_user_orders_with_products()  # assume this function exists
    if not user_orders:
        raise ValueError("No user orders found.")
    
    # Optional: avg_basket() if defined
    # avg_basket()

    # 2. Limit to top K products
    print(f"\n[2/6] Selecting top {top_k_products} most frequent products...")
    top_products = get_top_products(user_orders, top_k=top_k_products)
    print(f"Selected {len(top_products)} products (no 'other' token)")

    # 3. Encode products (no "other")
    product_to_idx, idx_to_product, num_classes, other_token = encode_products_limited(
        [], top_products
    )
    print(f"Number of output classes (including padding): {num_classes}")
    print(f"Note: index 0 = padding, indices 1..{num_classes-1} = real products")

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

    # Class weights (optional)
    pos_count = np.sum(y_train)
    neg_count = y_train.size - pos_count
    pos_weight = neg_count / max(pos_count, 1)
    print(f"Positive weight: {pos_weight:.2f}")

    # 7. Build model (time_input now has shape (max_seq_len, 1))
    print("\n[5/6] Building LSTM model...")
    product_input = keras.Input(shape=(max_seq_len,), name='product_input')
    time_input = keras.Input(shape=(max_seq_len, 1), name='time_input')   # single time feature
    user_input = keras.Input(shape=(1,), name='user_input')

    prod_embed = keras.layers.Embedding(
        input_dim=num_classes,      # indices 0..num_classes-1 (0 is padding)
        output_dim=64,
        mask_zero=True,
        name='prod_emb'
    )(product_input)

    # Concatenate along feature axis
    combined = keras.layers.Concatenate(axis=-1)([prod_embed, time_input])   # (batch, seq, 64+1)

    lstm_out = keras.layers.LSTM(64, dropout=0.2, return_sequences=True, name='lstm')(combined)
    attention = keras.layers.MultiHeadAttention(num_heads=4, key_dim=32, name='attention')(lstm_out, lstm_out)

    # Recency weights (adjust to your max_seq_len)
    recency_weights = tf.linspace(0.1, 0.5, max_seq_len)  # linear increase
    recency_weights = tf.reshape(recency_weights, (1, -1, 1))
    weighted_attention = attention * recency_weights
    attention_pooled = keras.layers.GlobalAveragePooling1D()(weighted_attention)

    user_embed = keras.layers.Embedding(input_dim=num_users, output_dim=16, name='user_emb')(user_input)
    user_flat = keras.layers.Flatten()(user_embed)

    merged = keras.layers.Concatenate()([attention_pooled, user_flat])
    dense = keras.layers.Dense(32, activation='relu')(merged)
    dropout = keras.layers.Dropout(0.1)(dense)

    output_size = num_classes   # predict probabilities for all classes (including padding, but we will ignore 0)
    output = keras.layers.Dense(output_size, activation='sigmoid', name='output')(dropout)

    model = keras.Model(inputs=[product_input, time_input, user_input], outputs=output)

    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',   # standard BCE, focal loss can be added later
        metrics=[
            'binary_accuracy',
            keras.metrics.Precision(thresholds=0.5),
            keras.metrics.Recall(thresholds=0.5)
        ]
    )
    model.summary()

    callbacks = [
        keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True, verbose=1),
        keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, verbose=1),
        keras.callbacks.ModelCheckpoint('ml/recommendation/final/checkpoint/sigmoid_checkpoint.keras',
                                        monitor='val_loss', save_best_only=True)
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
        verbose=1,
    )

    # Evaluation
    val_loss, val_bin_acc, val_prec, val_rec = model.evaluate([X_prod_val, X_time_val, user_val], y_val, verbose=0)
    print(f"\nValidation: loss={val_loss:.4f}, binary_accuracy={val_bin_acc:.4f}, precision={val_prec:.4f}, recall={val_rec:.4f}")

    # Multi-label ranking metrics
    from sklearn.metrics import average_precision_score, label_ranking_average_precision_score
    y_pred_proba = model.predict([X_prod_val, X_time_val, user_val], verbose=0)
    ap_list = []
    for i in range(y_val.shape[1]):
        if len(np.unique(y_val[:, i])) > 1:
            ap_list.append(average_precision_score(y_val[:, i], y_pred_proba[:, i]))
    map_score = np.mean(ap_list) if ap_list else 0.0
    lrap_score = label_ranking_average_precision_score(y_val, y_pred_proba)
    print(f"Mean AP (per-class): {map_score:.4f}")
    print(f"Label Ranking AP: {lrap_score:.4f}")

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
            'other_token': other_token,   # will be None
            'top_k_products': top_k_products
        }
        with open(mappings_save_path, 'wb') as f:
            pickle.dump(mappings, f)
        print("Mappings saved.")

    return model, product_to_idx, idx_to_product, user_to_idx, idx_to_user, history

# ------------------------------------------------------------
#  Recommendation function
# ------------------------------------------------------------
def recommend_next_items_sigmoid(
    user_id, user_history_products, user_history_timestamps,
    model, product_to_idx, idx_to_product, user_to_idx,
    max_seq_len=7, top_k=5, normalize=True,
):
    """
    Returns list of (product_id, probability) for top-k products.
    Skips padding (index 0) and any rare product that maps to 0.
    """
    # Process history
    if len(user_history_products) > max_seq_len:
        user_history_products = user_history_products[-max_seq_len:]
        user_history_timestamps = user_history_timestamps[-max_seq_len:]

    # Pad sequences (left pad with zeros)
    user_history_products = pad_sequences(
        [user_history_products],
        maxlen=max_seq_len,
        padding='pre',
        truncating='pre',
        value=0
    )[0]

    # Time features: need reference timestamp (oldest in truncated sequence)
    if user_history_timestamps and len(user_history_timestamps) > 0:
        ref_ts = min(user_history_timestamps)
    else:
        ref_ts = None

    pad_len = max_seq_len - len(user_history_timestamps)
    if pad_len > 0:
        user_history_timestamps = [0.0] * pad_len + user_history_timestamps

    # Encode products (rare -> 0)
    encoded_prods = []
    for p in user_history_products:
        if p == 0:
            encoded_prods.append(0)
        else:
            encoded_prods.append(product_to_idx.get(p, 0))

    # Single time feature per step
    time_feats = []
    for ts in user_history_timestamps:
        if ts == 0.0 or ref_ts is None:
            time_feats.append(0.0)
        else:
            time_feats.append(extract_temporal_features(ts, ref_ts))

    # Reshape for model
    prod_input = np.array([encoded_prods], dtype=np.int32)
    time_input = np.array([time_feats], dtype=np.float32).reshape(1, max_seq_len, 1)
    user_enc = user_to_idx.get(user_id, 0)
    user_input = np.array([[user_enc]], dtype=np.int32)

    predictions = model.predict([prod_input, time_input, user_input], verbose=0)[0]

    # Exclude padding index 0 from recommendations
    valid_indices = [i for i in range(len(predictions)) if i != 0 and i in idx_to_product]
    top_indices = sorted(valid_indices, key=lambda i: predictions[i], reverse=True)[:top_k]

    raw_scores = [float(predictions[i]) for i in top_indices]
    if normalize and raw_scores and sum(raw_scores) > 0:
        total = sum(raw_scores)
        normalized_scores = [s / total for s in raw_scores]
    else:
        normalized_scores = raw_scores

    return [(idx_to_product[i], normalized_scores[idx]) for idx, i in enumerate(top_indices)]


# =========
# custom loss function (not in use)
# =========
from keras.saving import register_keras_serializable
register_keras_serializable('Custom', name='focal_loss')
def focal_loss(gamma=2.0, alpha=0.5):  # alpha small because positives are rare
    def focal_loss_fn(y_true, y_pred):
        y_pred = tf.clip_by_value(y_pred, 1e-7, 1 - 1e-7)
        
        ce = -y_true * tf.math.log(y_pred) - (1 - y_true) * tf.math.log(1 - y_pred)
        pt = y_true * y_pred + (1 - y_true) * (1 - y_pred)
        modulating_factor = tf.pow(1 - pt, gamma)
        alpha_factor = y_true * alpha + (1 - y_true) * (1 - alpha)
        
        loss = alpha_factor * modulating_factor * ce
        return tf.reduce_mean(loss)
    return focal_loss_fn


# =====
# stats
# =====
def avg_basket():
    # Get all paid orders with their total item count (across all producers)
    orders = OrderPayment.objects.filter(
        payment_status='paid'
    ).annotate(
        # Sum up quantities OR count unique product lines – you decide
        total_quantity=Sum('producer_orders__order_items__quantity'),
        unique_products=Count('producer_orders__order_items__product', distinct=True),
        item_lines=Count('producer_orders__order_items')  # each OrderItem row
    )
    
    # Average basket size based on quantity (total units)
    avg_quantity = orders.aggregate(avg=Avg('total_quantity'))['avg']
    print(f"Average total quantity per order: {avg_quantity:.2f} units")
    
    # Average unique products per order
    avg_unique = orders.aggregate(avg=Avg('unique_products'))['avg']
    print(f"Average unique products per order: {avg_unique:.2f} products")
    
    # Average OrderItem rows (each product once, regardless of quantity)
    avg_lines = orders.aggregate(avg=Avg('item_lines'))['avg']
    print(f"Average product lines (rows) per order: {avg_lines:.2f}")