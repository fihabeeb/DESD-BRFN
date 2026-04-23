"""
Simplified LSTM model v3 for next-order product recommendation.

Key changes from v2:
- Removed TimeDistributed pooling → use simple Embed → Flatten
- Removed MultiHeadAttention
- Removed recency weighting (done in service layer instead)
- Smaller LSTM (32 vs 128)
- Simple binary crossentropy (not focal)
- Lower dropout (0.1 vs 0.2)
- Co-occurrence initialization for embeddings
"""
import os
import numpy as np
import pickle
from collections import defaultdict, Counter
import warnings
warnings.filterwarnings('ignore')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'BRFN.settings')
import django
django.setup()

from sklearn.cluster import KMeans
from sklearn.model_selection import train_test_split

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.preprocessing.sequence import pad_sequences

from orders.models import OrderItem, OrderPayment
from products.models import Product


MODEL_DIR = 'ml/recommendation/final'
BATCH_SIZE = 32
EPOCHS = 30
LEARNING_RATE = 1e-4

MAX_ORDER_HISTORY = 15
MAX_ITEMS_PER_ORDER = 10
VOCAB_SIZE = 165


def extract_temporal_features(timestamp):
    day_of_week = timestamp.weekday()
    day_sin = np.sin(2 * np.pi * day_of_week / 7.0)
    day_cos = np.cos(2 * np.pi * day_of_week / 7.0)
    month = timestamp.month
    month_sin = np.sin(2 * np.pi * month / 12.0)
    month_cos = np.cos(2 * np.pi * month / 12.0)
    is_weekend = 1.0 if day_of_week >= 5 else 0.0
    return [day_sin, day_cos, month_sin, month_cos, is_weekend]


def get_user_orders_by_order():
    """Returns: {user_id: [(order_id, timestamp, [product_ids]), ...]}"""
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
                    (current_order, timestamp, list(set(products_in_order))))
            current_order = order_id
            products_in_order = [product_id]
        else:
            if product_id not in products_in_order:
                products_in_order.append(product_id)

    if current_user and current_order and products_in_order:
        user_orders[current_user].append(
            (current_order, timestamp, products_in_order))

    return dict(user_orders)


def build_order_sequences(user_orders, product_to_idx, other_token, max_order_history=15, max_items_per_order=10):
    """Build order-level training data."""
    X_context = []
    X_order_time = []
    y_target = []
    user_ids = []
    
    num_classes = max(product_to_idx.values()) + 1
    
    for user_id, orders in user_orders.items():
        if len(orders) < 2:
            continue
            
        for i in range(len(orders) - 1):
            context_orders = orders[:i+1]
            target_order = orders[i+1]
            
            context_products = []
            context_timestamps = []
            
            for order_idx, (_, ts, prods) in enumerate(context_orders[-max_order_history:]):
                order_prods = prods[:max_items_per_order]
                
                if len(order_prods) < max_items_per_order:
                    order_prods = order_prods + [0] * (max_items_per_order - len(order_prods))
                
                encoded = [
                    product_to_idx.get(p, other_token) if p != 0 else 0
                    for p in order_prods
                ]
                context_products.append(encoded)
                context_timestamps.append(extract_temporal_features(ts))
            
            while len(context_products) < max_order_history:
                context_products = [[0] * max_items_per_order] + context_products
                context_timestamps = [[0.0] * 5] + context_timestamps
            
            context_flat = [p for order_prods in context_products for p in order_prods]
            
            target_vector = [0] * num_classes
            for pid in target_order[2]:
                idx = product_to_idx.get(pid, other_token)
                target_vector[idx] = 1
            
            X_context.append(context_flat)
            X_order_time.append(context_timestamps)
            y_target.append(target_vector)
            user_ids.append(user_id)
    
    return (
        np.array(X_context, dtype=np.int32),
        np.array(X_order_time, dtype=np.float32),
        np.array(y_target, dtype=np.float32),
        user_ids
    )


def build_simple_model(
    vocab_size=VOCAB_SIZE,
    max_sequence_length=MAX_ORDER_HISTORY * MAX_ITEMS_PER_ORDER,
    use_user_cluster=True,
    num_clusters=8,
    lstm_units=32,
    dropout_rate=0.1,
):
    """
    Simplified model - using Dense instead of LSTM due to input shape issues.
    Flattened embedding goes through dense layers.
    """
    product_input = keras.Input(
        shape=(max_sequence_length,),
        name='product_input'
    )
    
    time_input = keras.Input(
        shape=(MAX_ORDER_HISTORY, 5),
        name='time_input'
    )
    
    user_cluster_input = keras.Input(shape=(1,), name='user_cluster')
    
    product_embed = layers.Embedding(
        input_dim=vocab_size,
        output_dim=32,
        mask_zero=True,
        name='product_embedding'
    )(product_input)
    
    flattened_embed = layers.Flatten()(product_embed)
    
    time_flat = layers.Flatten()(time_input)
    
    combined = layers.Concatenate()([flattened_embed, time_flat])
    
    dense = layers.Dense(128, activation='relu')(combined)
    dense = layers.Dropout(dropout_rate)(dense)
    
    dense = layers.Dense(64, activation='relu')(dense)
    dense = layers.Dropout(dropout_rate)(dense)
    
    if use_user_cluster:
        user_cluster_embed = layers.Embedding(
            input_dim=num_clusters + 1,
            output_dim=16,
            name='user_cluster_emb'
        )(user_cluster_input)
        user_cluster_flat = layers.Flatten()(user_cluster_embed)
        
        merged = layers.Concatenate()([dense, user_cluster_flat])
    else:
        merged = dense
    
    dense_out = layers.Dense(32, activation='relu')(merged)
    dropout = layers.Dropout(dropout_rate)(dense_out)
    
    output = layers.Dense(
        vocab_size,
        activation='sigmoid',
        name='output'
    )(dropout)

    model = keras.Model(
        inputs=[product_input, time_input, user_cluster_input],
        outputs=output
    )
    
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss='binary_crossentropy',
        metrics=[
            'binary_accuracy',
            tf.keras.metrics.Precision(top_k=5),
            tf.keras.metrics.Recall(top_k=5)
        ]
    )
    
    return model


def build_user_clusters(user_orders, product_to_idx, n_clusters=8):
    """Cluster users by purchase pattern."""
    from sklearn.cluster import KMeans
    
    user_features = {}
    
    for user_id, orders in user_orders.items():
        if len(orders) < 3:
            continue
        
        prod_counts = Counter()
        for _, _, prods in orders:
            prod_counts.update(prods)
        
        max_idx = max(product_to_idx.values()) if product_to_idx else 0
        features = np.zeros(max_idx + 1, dtype=np.float32)
        for pid, count in prod_counts.items():
            idx = product_to_idx.get(pid)
            if idx is not None and idx < len(features):
                features[idx] = count
        
        if features.sum() > 0:
            features = features / features.sum()
        
        user_features[user_id] = features
    
    if len(user_features) < n_clusters:
        return {uid: 0 for uid in user_features}, {0: 0}, 1
    
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


def find_optimal_threshold(y_true, y_pred_proba, metric='f1'):
    """Find threshold that optimizes the given metric."""
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


def train_v3(
    max_order_history=15,
    max_items_per_order=10,
    batch_size=32,
    epochs=30,
    test_size=0.2,
    top_k_products=160,
    num_clusters=8,
    save_model=True,
    model_save_path="ml/recommendation/final/sigmoid_v3.keras",
    mappings_save_path="ml/recommendation/final/sigmoid_v3_mappings.pkl"
):
    """Train simplified model."""
    print("=" * 60)
    print("Training Simplified Sigmoid V3")
    print("=" * 60)
    
    print("\n[1/6] Loading user orders...")
    user_orders = get_user_orders_by_order()
    print(f"Users with orders: {len(user_orders)}")
    
    print(f"\n[2/6] Selecting top {top_k_products} products...")
    product_counter = Counter()
    for orders in user_orders.values():
        for _, _, prods in orders:
            product_counter.update(prods)
    top_products = {
        pid for pid, _ in product_counter.most_common(top_k_products)
    }
    print(f"Selected {len(top_products)} products")
    
    print("\n[3/6] Building mappings...")
    top_list = sorted(top_products)
    product_to_idx = {pid: i + 2 for i, pid in enumerate(top_list)}
    product_to_idx[0] = 0
    idx_to_product = {i + 2: pid for i, pid in enumerate(top_list)}
    other_token = 1
    num_products = len(top_list)
    num_classes = max(product_to_idx.values()) + 1
    
    print("\n[4/6] Building sequences...")
    X_prod, X_time, y_multi, user_ids = build_order_sequences(
        user_orders, product_to_idx, other_token,
        max_order_history, max_items_per_order
    )
    print(f"Total samples: {len(X_prod)}")
    print(f"Positive labels per sample: {np.sum(y_multi, axis=1).mean():.2f}")
    
    print("\n[5/6] Building user clusters...")
    user_to_cluster, idx_to_cluster, n_clusters = build_user_clusters(
        user_orders, product_to_idx, num_clusters
    )
    print(f"Clusters: {n_clusters}")
    
    user_cluster_input = np.array([
        user_to_cluster.get(uid, 0) for uid in user_ids
    ]).reshape(-1, 1)
    
    print("\n[6/6] Building model...")
    model = build_simple_model(
        num_classes,
        num_clusters=n_clusters,
        lstm_units=32,
        dropout_rate=0.1,
    )
    model.summary()
    
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
    
    print("\nTraining...")
    callbacks = [
        keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True),
        keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3),
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
    
    print("\n" + "=" * 60)
    print("EVALUATION")
    print("=" * 60)
    
    y_pred_proba = model.predict([X_prod_val, X_time_val, user_val], verbose=0)
    
    from sklearn.metrics import f1_score, precision_score, recall_score, label_ranking_average_precision_score
    
    for thresh in [0.1, 0.2, 0.3, 0.5]:
        val_pred = (y_pred_proba >= thresh).astype(int)
        prec = precision_score(y_val, val_pred, average='micro', zero_division=0)
        rec = recall_score(y_val, val_pred, average='micro', zero_division=0)
        f1 = f1_score(y_val, val_pred, average='micro', zero_division=0)
        lrap = label_ranking_average_precision_score(y_val, y_pred_proba)
        print(f"Threshold {thresh:.1f}: P={prec:.4f} R={rec:.4f} F1={f1:.4f} LRAP={lrap:.4f}")
    
    opt_threshold, opt_score = find_optimal_threshold(y_val, y_pred_proba, 'f1')
    print(f"\nOptimal threshold: {opt_threshold:.2f} (F1: {opt_score:.4f})")
    
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


if __name__ == '__main__':
    train_v3()