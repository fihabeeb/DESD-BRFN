"""
Enhanced sigmoid LSTM model v2.
Features:
1. Order-level training (predict next order's products)
2. Product co-occurrence embedding
3. User clustering
4. Threshold optimization for F1
"""
import numpy as np
import tensorflow as tf
from tensorflow import keras
from collections import defaultdict, Counter
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.sequence import pad_sequences
import pickle
import datetime
import logging
import os

logger = logging.getLogger(__name__)

from django.db.models import Window, F
from django.db.models.functions import RowNumber

from orders.models import OrderItem, OrderPayment
from django.db.models import Sum, Count, Avg


# ------------------------------------------------------------
# Helper: extract temporal features
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
# Data extraction: GROUP BY ORDER (not flattened)
# ------------------------------------------------------------
def get_user_orders_by_order():
    """
    Returns: {user_id: [(order_id, timestamp, [product_ids]), ...]}
    Each product appears once per order (deduplicated for multi-label target)
    Sorted: oldest → newest (for LSTM)
    """
    user_orders = defaultdict(list)
    
    order_items = OrderItem.objects.filter(
        producer_order__payment__payment_status='paid'
    ).exclude(
        producer_order__payment__user__customer_profile__id__range=(1,5)
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
                user_orders[current_user].append(
                    (current_order, timestamp, list(set(products_in_order)))
                )
            current_order = order_id
            products_in_order = [product_id]
        else:
            if product_id not in products_in_order:
                products_in_order.append(product_id)

    if current_user and current_order and products_in_order:
        user_orders[current_user].append(
            (current_order, timestamp, products_in_order))

    return dict(user_orders)


# ------------------------------------------------------------
# Build order-level sequences
# ------------------------------------------------------------
def build_order_sequences(user_orders, product_to_idx, other_token, max_order_history=15, max_items_per_order=10):
    """
    Build order-level training data.
    
    Args:
        user_orders: {user_id: [(order_id, timestamp, [product_ids]), ...]}
        product_to_idx: product ID → index
        other_token: index for unknown products
        max_order_history: how many past orders to use as context
        max_items_per_order: max items to consider per order
        
    Returns:
        X_context: order-level sequences (batch, max_order_history * max_items_per_order)
        X_order_time: temporal features per order
        X_order_sizes: number of items per order (for masking)
        y_target: multi-hot target for next order
        user_ids: user IDs
    """
    X_context = []
    X_order_time = []
    X_order_sizes = []
    y_target = []
    user_ids = []
    
    num_classes = max(product_to_idx.values()) + 1  # includes padding + other + real products
    
    for user_id, orders in user_orders.items():
        if len(orders) < 2:
            continue
            
        # Use last max_order_history orders as input, predict the order after
        for i in range(len(orders) - 1):
            context_orders = orders[:i+1]
            target_order = orders[i+1]
            
            # Collect context products from past orders
            context_products = []
            context_timestamps = []
            order_sizes = []
            
            for order_idx, (_, ts, prods) in enumerate(context_orders[-max_order_history:]):
                # Take up to max_items_per_order from each order
                order_prods = prods[:max_items_per_order]
                order_sizes.append(len(order_prods))
                
                # Pad if needed
                if len(order_prods) < max_items_per_order:
                    order_prods = order_prods + [0] * (max_items_per_order - len(order_prods))
                
                # Encode products
                encoded = [
                    product_to_idx.get(p, other_token) if p != 0 else 0
                    for p in order_prods
                ]
                context_products.append(encoded)
                context_timestamps.append(extract_temporal_features(ts))
            
            # Pad orders if needed
            while len(context_products) < max_order_history:
                context_products = [[0] * max_items_per_order] + context_products
                context_timestamps = [[0.0] * 5] + context_timestamps
                order_sizes = [0] + order_sizes
            
            # Flatten to single sequence (batch_size, max_order_history * max_items_per_order)
            context_flat = [p for order_prods in context_products for p in order_prods]
            timestamps_flat = context_timestamps
            
            # Target: multi-hot for next order
            target_vector = [0] * num_classes
            for pid in target_order[2]:
                idx = product_to_idx.get(pid, other_token)
                target_vector[idx] = 1
            
            X_context.append(context_flat)
            X_order_time.append(timestamps_flat)
            X_order_sizes.append(order_sizes)
            y_target.append(target_vector)
            user_ids.append(user_id)
    
    return (
        np.array(X_context, dtype=np.int32),
        np.array(X_order_time, dtype=np.float32),
        np.array(X_order_sizes, dtype=np.int32),
        np.array(y_target, dtype=np.float32),
        user_ids
    )


# ------------------------------------------------------------
# Build co-occurrence embedding from training data
# ------------------------------------------------------------
def build_cooccurrence_from_orders(user_orders, product_to_idx, window_orders=3):
    """Build product co-occurrence scores for embedding init."""
    cooc = defaultdict(lambda: defaultdict(float))
    
    for user_id, orders in user_orders.items():
        for i, (_, _, prods_i) in enumerate(orders):
            for j in range(i + 1, min(i + 1 + window_orders, len(orders))):
                _, _, prods_j = orders[j]
                
                # Weight decays with order distance
                weight = 0.8 ** (j - i - 1)
                
                for p_i in prods_i:
                    for p_j in prods_j:
                        if p_i != p_j:
                            idx_i = product_to_idx.get(p_i)
                            idx_j = product_to_idx.get(p_j)
                            if idx_i and idx_j:
                                cooc[idx_i][idx_j] += weight
    
    num_products = len(product_to_idx)
    cooc_matrix = np.zeros((num_products, num_products), dtype=np.float32)
    
    for idx_i, targets in cooc.items():
        for idx_j, weight in targets.items():
            cooc_matrix[idx_i, idx_j] = weight
    
    # Row-normalize
    row_sums = cooc_matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    cooc_matrix = cooc_matrix / row_sums
    
    return cooc_matrix


# ------------------------------------------------------------
# Build user clusters from order history
# ------------------------------------------------------------
def build_user_clusters(user_orders, product_to_idx, n_clusters=8):
    """Cluster users by purchase pattern similarity."""
    from sklearn.cluster import KMeans
    
    user_features = {}
    
    # Build feature vectors
    for user_id, orders in user_orders.items():
        if len(orders) < 3:
            continue
        
        # Product preference vector
        prod_counts = Counter()
        for _, _, prods in orders:
            prod_counts.update(prods)
        
        # Aggregate into fixed-size vector
        # product_to_idx starts from 2, need array size to match
        max_idx = max(product_to_idx.values()) if product_to_idx else 0
        features = np.zeros(max_idx + 1, dtype=np.float32)
        for pid, count in prod_counts.items():
            idx = product_to_idx.get(pid)
            if idx is not None and idx < len(features):
                features[idx] = count
        
        # Normalize
        if features.sum() > 0:
            features = features / features.sum()
        
        user_features[user_id] = features
    
    if len(user_features) < n_clusters:
        # Assign all to same cluster
        return {uid: 0 for uid in user_features}, {0: 0}, n_clusters
    
    # KMeans clustering
    X = np.array(list(user_features.values()))
    
    kmeans = KMeans(n_clusters=min(n_clusters, len(user_features)), random_state=42, n_init=3)
    labels = kmeans.fit_predict(X)
    
    user_to_cluster = {
        uid: labels[i] 
        for i, uid in enumerate(sorted(user_features.keys()))
    }
    n_unique_clusters = len(set(labels))
    idx_to_cluster = {i: i for i in range(n_unique_clusters)}
    
    return user_to_cluster, idx_to_cluster, n_unique_clusters


# ------------------------------------------------------------
# ENHANCED MODEL: Order-level LSTM with co-occurrence + clustering
# ------------------------------------------------------------
def build_enhanced_model(
    num_classes,
    num_clusters,
    cooc_embedding_dim=16,
    max_order_history=15,
    max_items_per_order=10,
    lstm_units=128,
    recurrent_dropout=0.2,
    dense_units=64
):
    """
    Build enhanced LSTM model with:
    - Order-level input (flattened from multiple orders)
    - Co-occurrence embedding
    - User cluster embedding
    """
    # Inputs
    product_input = keras.Input(
        shape=(max_order_history * max_items_per_order,), 
        name='product_input'
    )
    time_input = keras.Input(
        shape=(max_order_history, 5), 
        name='time_input'
    )
    user_cluster_input = keras.Input(shape=(1,), name='user_cluster')
    
    # Product embedding with co-occurrence init
    prod_embed = keras.layers.Embedding(
        input_dim=num_classes + 1,
        output_dim=64,
        mask_zero=True,
        name='prod_emb'
    )(product_input)
    
    # Reshape for order-level attention
    prod_reshaped = keras.layers.Reshape(
        (max_order_history, max_items_per_order, 64)
    )(prod_embed)
    
    # Order-level attention (attention across orders)
    # Reduce item dimension first
    prod_pooled = keras.layers.TimeDistributed(
        keras.layers.GlobalAveragePooling1D()
    )(prod_reshaped)  # (batch, max_order_history, 64)
    
    # Temporal features per order
    time_pooled = keras.layers.TimeDistributed(
        keras.layers.Dense(16, activation='relu')
    )(time_input)  # (batch, max_order_history, 16)
    
    # Combine product and time
    combined = keras.layers.Concatenate()([prod_pooled, time_pooled])
    
    # LSTM across orders
    lstm_out = keras.layers.LSTM(
        lstm_units,
        dropout=0.2,
        recurrent_dropout=recurrent_dropout,
        return_sequences=True
    )(combined)
    
    # Self-attention across orders
    attention = keras.layers.MultiHeadAttention(
        num_heads=4, 
        key_dim=32
    )(lstm_out, lstm_out)

    # Order recency weighting (recent orders matter more)
    # Normalize so weights sum to 1 across sequence
    order_weights = tf.constant(
        [0.02, 0.03, 0.04, 0.05, 0.07, 0.09, 0.12, 0.15, 0.20, 0.28, 0.35, 0.42, 0.50, 0.58, 0.65][:max_order_history],
        dtype=tf.float32
    )
    order_weights = order_weights / tf.reduce_sum(order_weights)
    weighted = attention * order_weights[tf.newaxis, :, tf.newaxis]
    attention_pooled = keras.layers.GlobalAveragePooling1D()(weighted)
    
    # User cluster embedding
    user_cluster_embed = keras.layers.Embedding(
        input_dim=num_clusters + 1,
        output_dim=16,
        name='user_cluster_emb'
    )(user_cluster_input)
    user_cluster_flat = keras.layers.Flatten()(user_cluster_embed)
    
    # Merge all features
    merged = keras.layers.Concatenate()([attention_pooled, user_cluster_flat])
    
    # Dense layers
    dense = keras.layers.Dense(dense_units, activation='relu')(merged)
    dropout = keras.layers.Dropout(0.2)(dense)
    
    # Output: multi-label sigmoid (num_classes = 0+1+164 = 166)
    output = keras.layers.Dense(
        num_classes,
        activation='sigmoid',
        name='output'
    )(dropout)
    
    model = keras.Model(
        inputs=[product_input, time_input, user_cluster_input],
        outputs=output
    )
    
    model.compile(
        optimizer='adam',
        loss=tf.keras.losses.BinaryFocalCrossentropy(gamma=1.0, alpha=0.75),
        metrics=[
            'binary_accuracy',
            tf.keras.metrics.Precision(top_k=5),
            tf.keras.metrics.Recall(top_k=5)
        ]
    )
    
    return model


# ------------------------------------------------------------
# Optimized threshold for F1
# ------------------------------------------------------------
def find_optimal_threshold(y_true, y_pred_proba, metric='f1'):
    """
    Find threshold that optimizes the given metric.
    """
    from sklearn.metrics import f1_score, precision_score, recall_score
    
    best_threshold = 0.5
    best_score = 0
    
    for threshold in np.arange(0.1, 0.9, 0.05):
        y_pred = (y_pred_proba >= threshold).astype(int)
        
        f1 = f1_score(y_true, y_pred, average='micro', zero_division=0)
        prec = precision_score(y_true, y_pred, average='micro', zero_division=0)
        rec = recall_score(y_true, y_pred, average='micro', zero_division=0)
        
        if metric == 'f1':
            score = f1
        elif metric == 'precision':
            score = prec
        elif metric == 'recall':
            score = rec
        else:
            score = 2 * prec * rec / (prec + rec + 1e-8)
        
        if score > best_score:
            best_score = score
            best_threshold = threshold
    
    return best_threshold, best_score


# ------------------------------------------------------------
# MAIN: Train enhanced model
# ------------------------------------------------------------
def train_enhanced_sigmoid_lstm(
    max_order_history=15,
    max_items_per_order=10,
    batch_size=32,
    epochs=25,
    test_size=0.2,
    top_k_products=200,
    num_clusters=8,
    save_model=True,
    model_save_path="ml/recommendation/final/sigmoid_v2.keras",
    mappings_save_path="ml/recommendation/final/sigmoid_v2_mappings.pkl"
):
    """
    Train enhanced sigmoid LSTM with order-level prediction.
    """
    print("=" * 60)
    print("Training Enhanced Sigmoid LSTM (Order-Level)")
    print("=" * 60)
    
    # 1. Load data grouped by order
    print("\n[1/7] Loading user orders...")
    user_orders = get_user_orders_by_order()
    print(f"Users with orders: {len(user_orders)}")
    
    # 2. Get top products
    print(f"\n[2/7] Selecting top {top_k_products} products...")
    product_counter = Counter()
    for orders in user_orders.values():
        for _, _, prods in orders:
            product_counter.update(prods)
    top_products = {
        pid for pid, _ in product_counter.most_common(top_k_products)
    }
    print(f"Selected {len(top_products)} products")
    
    # 3. Build product mappings
    top_list = sorted(top_products)
    product_to_idx = {pid: i + 2 for i, pid in enumerate(top_list)}
    product_to_idx[0] = 0
    idx_to_product = {i + 2: pid for i, pid in enumerate(top_list)}
    other_token = 1
    num_products = len(top_list)
    num_classes = max(product_to_idx.values()) + 1  # 0(pad) + 1(other) + 164 = 166
    
    # 4. Build sequences
    print("\n[3/7] Building order-level sequences...")
    X_prod, X_time, X_sizes, y_multi, user_ids = build_order_sequences(
        user_orders, product_to_idx, other_token,
        max_order_history, max_items_per_order
    )
    print(f"Total samples: {len(X_prod)}")
    print(f"Positive labels per sample: {np.sum(y_multi, axis=1).mean():.2f}")
    
    # 5. Build user clusters
    print("\n[4/7] Building user clusters...")
    user_to_cluster, idx_to_cluster, n_clusters = build_user_clusters(
        user_orders, product_to_idx, num_clusters
    )
    
    # Map users to cluster indices
    user_cluster_input = np.array([
        user_to_cluster.get(uid, 0) for uid in user_ids
    ]).reshape(-1, 1)
    
    # 6. Train/val split
    print("\n[5/7] Splitting data...")
    indices = np.arange(len(X_prod))
    train_idx, val_idx = train_test_split(indices, test_size=test_size, random_state=42)
    
    X_prod_train = X_prod[train_idx]
    X_prod_val = X_prod[val_idx]
    X_time_train = X_time[train_idx]
    X_time_val = X_time[val_idx]
    user_train = user_cluster_input[train_idx]
    user_val = user_cluster_input[val_idx]
    y_train = y_multi[train_idx]
    y_val = y_multi[val_idx]
    
    # 7. Build model
    print("\n[6/7] Building enhanced model...")
    model = build_enhanced_model(
        num_classes=num_classes,
        num_clusters=n_clusters,
        max_order_history=max_order_history,
        max_items_per_order=max_items_per_order,
        lstm_units=128,
        recurrent_dropout=0.2,
        dense_units=64
    )
    model.summary()
    
    # 8. Train
    print("\n[7/7] Training...")
    callbacks = [
        keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True),
        keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3),
        keras.callbacks.ModelCheckpoint(
            'ml/recommendation/final/checkpoint/sigmoid_v2_checkpoint.keras',
            monitor='val_loss', save_best_only=True
        )
    ]
    
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
    print("\n" + "=" * 60)
    print("EVALUATION")
    print("=" * 60)
    
    y_pred_proba = model.predict([X_prod_val, X_time_val, user_val], verbose=0)
    
    # Default threshold
    val_pred = (y_pred_proba >= 0.5).astype(int)
    from sklearn.metrics import f1_score, precision_score, recall_score, label_ranking_average_precision_score
    
    prec = precision_score(y_val, val_pred, average='micro', zero_division=0)
    rec = recall_score(y_val, val_pred, average='micro', zero_division=0)
    f1 = f1_score(y_val, val_pred, average='micro', zero_division=0)
    lrap = label_ranking_average_precision_score(y_val, y_pred_proba)
    
    print(f"At threshold 0.5:")
    print(f"  Precision: {prec:.4f}")
    print(f"  Recall: {rec:.4f}")
    print(f"  F1: {f1:.4f}")
    print(f"  LRAP: {lrap:.4f}")
    
    # Optimize threshold
    opt_threshold, opt_score = find_optimal_threshold(y_val, y_pred_proba, 'f1')
    print(f"\nOptimal threshold: {opt_threshold:.2f} (F1: {opt_score:.4f})")
    
    # Save
    if save_model:
        print(f"\nSaving model to {model_save_path}")
        model.save(model_save_path)
        
        mappings = {
            'product_to_idx': product_to_idx,
            'idx_to_product': idx_to_product,
            'user_to_cluster': user_to_cluster,
            'idx_to_cluster': idx_to_cluster,
            'num_products': num_products,
            'num_clusters': n_clusters,
            'max_order_history': max_order_history,
            'max_items_per_order': max_items_per_order,
            'other_token': other_token,
            'optimal_threshold': opt_threshold,
        }
        with open(mappings_save_path, 'wb') as f:
            pickle.dump(mappings, f)
        print("Mappings saved.")
    
    return model, history, opt_threshold