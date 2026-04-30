"""
Sigmoid model v5 - Proper Sampled Softmax.

Approach:
- For each training sample: 1 positive + sampled negatives
- Train with SparseCategoricalCrossentropy
- At inference: score ALL products
"""
import os
import numpy as np
import pickle
from collections import defaultdict, Counter
import warnings
warnings.filterwarnings("ignore")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "BRFN.settings")
import django
django.setup()

from sklearn.cluster import KMeans
from sklearn.model_selection import train_test_split
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from orders.models import OrderItem

BATCH_SIZE = 64
EPOCHS = 30
LEARNING_RATE = 5e-4
MAX_ORDER_HISTORY = 15
MAX_ITEMS_PER_ORDER = 5
NUM_NEGATIVES = 10          # number of negative samples per positive

def extract_temporal_features(timestamp):
    day_of_week = timestamp.weekday()
    day_sin = np.sin(2 * np.pi * day_of_week / 7.0)
    day_cos = np.cos(2 * np.pi * day_of_week / 7.0)
    month = timestamp.month
    month_sin = np.sin(2 * np.pi * month / 12.0)
    month_cos = np.cos(2 * np.pi * month / 12.0)
    is_weekend = 1.0 if day_of_week >= 5 else 0.0
    return [day_sin, day_cos, month_sin, month_cos, is_weekend]

def get_user_orders():
    user_orders = defaultdict(list)
    order_items_query = OrderItem.objects.filter(
        producer_order__payment__payment_status="paid"
    ).exclude(
        producer_order__payment__user__customer_profile__id__range=(1,5)
    ).select_related("product", "producer_order__payment__user"
    ).order_by("producer_order__payment__created_at")
    
    print(f"DEBUG: Raw OrderItem query count: {order_items_query.count()}")
    
    all_users = set()
    all_orders = set()
    all_products = set()
    for item in order_items_query:
        all_users.add(item.producer_order.payment.user.id)
        all_orders.add(item.producer_order.payment.id)
        all_products.add(item.product.id)
    print(f"DEBUG: Unique users in query: {len(all_users)}")
    print(f"DEBUG: Unique orders in query: {len(all_orders)}")
    print(f"DEBUG: Unique products in query: {len(all_products)}")
    
    order_items = list(order_items_query)
    print(f"DEBUG: Order items evaluated: {len(order_items)}")
    
    current_user, current_order, products = None, None, []
    for item in order_items:
        user = item.producer_order.payment.user
        order_id = item.producer_order.payment.id
        timestamp = item.producer_order.payment.created_at
        product_id = item.product.id
        if user is None: continue
        if current_user != user.id:
            if current_user and current_order and products:
                user_orders[current_user].append((current_order, timestamp, list(set(products))))
            current_user, current_order, products = user.id, None, []
        if current_order != order_id:
            if current_order and products:
                user_orders[current_user].append((current_order, timestamp, list(set(products))))
            current_order, products = order_id, [product_id]
        else:
            if product_id not in products: products.append(product_id)
    if current_user and current_order and products:
        user_orders[current_user].append((current_order, timestamp, products))
    
    print(f"DEBUG: Users in user_orders dict: {len(user_orders)}")
    for uid, os in list(user_orders.items())[:3]:
        print(f"DEBUG: User {uid} has {len(os)} orders")
    return dict(user_orders)

def build_sequences_with_sampling(user_orders, product_to_idx, other_token, all_pids,
                                  max_hist=15, max_items=10, num_neg=10, seed=42):
    np.random.seed(seed)
    X_prod, X_time, y_labels, user_ids = [], [], [], []
    all_pids = list(all_pids)
    
    debug_stats = {'skip_no_orders': 0, 'skip_no_pos_idx': 0, 'skip_no_neg_pool': 0, 'total_orders_checked': 0}
    
    for uid, orders in user_orders.items():
        if len(orders) < 2:
            debug_stats['skip_no_orders'] += 1
            continue
        for i in range(len(orders) - 1):
            debug_stats['total_orders_checked'] += 1
            ctx = orders[:i+1]
            tgt = orders[i+1]
            ctx_prods, ctx_times = [], []
            for _, ts, ps in ctx[-max_hist:]:
                ps = ps[:max_items]
                if len(ps) < max_items:
                    ps = ps + [0] * (max_items - len(ps))
                enc = [product_to_idx.get(p, other_token) if p != 0 else 0 for p in ps]
                ctx_prods.append(enc)
                ctx_times.append(extract_temporal_features(ts))
            # Pad if needed
            while len(ctx_prods) < max_hist:
                ctx_prods = [[0]*max_items] + ctx_prods
                ctx_times = [[0.0]*5] + ctx_times
            
            # Positive products in target order
            pos_idx = [product_to_idx.get(p, other_token) for p in tgt[2] if p in product_to_idx]
            pos_idx = [p for p in pos_idx if p >= 2]   # ignore padding (0) and unknown (1)
            if not pos_idx:
                debug_stats['skip_no_pos_idx'] += 1
                continue
            
            # Negative sampling: products not in target order
            neg_pool = [p for p in all_pids if p not in tgt[2]]
            if len(neg_pool) < 1:
                debug_stats['skip_no_neg_pool'] += 1
                continue
                negs = np.random.choice(neg_pool, num_neg, replace=False)
            else:
                negs = neg_pool
            neg_idx = [product_to_idx.get(p, other_token) for p in negs if p in product_to_idx]
            neg_idx = [p for p in neg_idx if p >= 2][:num_neg]
            
            # For each positive product, create one training sample (with the full context)
            for pidx in pos_idx:
                # Keep the 3D shape (max_hist, max_items) – DO NOT flatten
                X_prod.append(ctx_prods)          # shape will be (max_hist, max_items)
                X_time.append(ctx_times)          # shape will be (max_hist, 5)
                y_labels.append(pidx)
                user_ids.append(uid)
    
    # Convert to numpy arrays
    X_prod = np.array(X_prod, dtype=np.int32)      # (n_samples, max_hist, max_items)
    X_time = np.array(X_time, dtype=np.float32)    # (n_samples, max_hist, 5)
    y_labels = np.array(y_labels, dtype=np.int32)
    
    print(f"DEBUG: {debug_stats}")
    print(f"DEBUG: all_pids count = {len(all_pids)}")
    print(f"Samples: {len(X_prod)}")
    
    return X_prod, X_time, y_labels, user_ids

def build_model(num_classes, vocab_size, max_hist=15, max_items=10, lstm_units=64, dropout=0.2):
    product_ids = keras.Input(shape=(max_hist, max_items), name="product_input")
    temporal = keras.Input(shape=(max_hist, 5), name="time_input")
    user_cluster = keras.Input(shape=(1,), name="user_cluster")
    
    # Embedding layer – mask_zero=True to ignore padding (0)
    emb = layers.Embedding(vocab_size, 32, mask_zero=True)(product_ids)
    # Reshape to (batch, max_hist, max_items*32)
    flat_emb = layers.Reshape((max_hist, max_items * 32))(emb)
    # Concatenate with temporal features
    combined = layers.Concatenate()([flat_emb, temporal])
    
    # LSTM that returns the last output (no attention)
    lstm_out = layers.LSTM(lstm_units, return_sequences=False)(combined)
    lstm_out = layers.Dropout(dropout)(lstm_out)
    
    # Cluster embedding (max cluster id is 8, but we set size to 10 to be safe)
    c_emb = layers.Embedding(10, 8)(user_cluster)
    merged = layers.Concatenate()([lstm_out, layers.Flatten()(c_emb)])
    
    x = layers.Dense(64, activation="relu")(merged)
    x = layers.Dropout(dropout)(x)
    x = layers.Dense(32, activation="relu")(x)
    x = layers.Dropout(dropout)(x)
    logits = layers.Dense(num_classes, name="logits")(x)   # num_classes = vocab_size
    
    model = keras.Model(inputs=[product_ids, temporal, user_cluster], outputs=logits)
    model.compile(
        optimizer=keras.optimizers.Adam(LEARNING_RATE),
        loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=[keras.metrics.SparseTopKCategoricalAccuracy(k=5)]
    )
    return model

def get_clusters(user_orders, product_to_idx, n_clusters=8):
    features = {}
    for uid, orders in user_orders.items():
        if len(orders) < 3: continue
        cnt = Counter()
        for _, _, ps in orders:
            cnt.update(ps)
        arr = np.zeros(max(product_to_idx.values()) + 1, dtype=np.float32)
        for p, c in cnt.items():
            i = product_to_idx.get(p)
            if i and i < len(arr):
                arr[i] = c
        if arr.sum() > 0:
            arr = arr / arr.sum()
        features[uid] = arr
    
    if len(features) < n_clusters:
        return {u: 0 for u in features}, 1
    
    X = np.array(list(features.values()))
    km = KMeans(min(n_clusters, len(X)), random_state=42, n_init=3)
    labels = km.fit_predict(X)
    return {u: labels[i] for i, u in enumerate(sorted(features.keys()))}, len(set(labels))

def train_v5():
    print("=" * 50)
    print("V5: LSTM with Sampled Softmax")
    print("=" * 50)
    
    print("\n[1] Loading orders...")
    user_orders = get_user_orders()
    print(f"Users loaded: {len(user_orders)}")
    
    total_orders = sum(len(orders) for orders in user_orders.values())
    print(f"DEBUG: Total user orders: {total_orders}")
    
    all_products = set()
    for orders in user_orders.values():
        for _, _, ps in orders:
            all_products.update(ps)
    print(f"DEBUG: Unique products in user_orders: {len(all_products)}")
    
    users_with_2plus = sum(1 for orders in user_orders.values() if len(orders) >= 2)
    print(f"DEBUG: Users with 2+ orders: {users_with_2plus}")
    
    print("\n[2] Building product mappings...")
    counter = Counter()
    for orders in user_orders.values():
        for _, _, prods in orders:
            counter.update(prods)
    print(f"DEBUG: Product frequency counter items: {len(counter)}")
    # Use top 160 most frequent products (indices 2..161), leaving 0 for padding, 1 for other
    top_products = {p for p, _ in counter.most_common(160)}
    product_to_idx = {p: i+2 for i, p in enumerate(sorted(top_products))}
    product_to_idx[0] = 0
    idx_to_product = {i+2: p for i, p in enumerate(sorted(top_products))}
    vocab_size = max(product_to_idx.values()) + 1   # should be 162
    num_classes = vocab_size                        # same for output layer
    
    print(f"Vocabulary size: {vocab_size}")
    print(f"Number of classes: {num_classes}")
    
    print("\n[3] Building sequences with negative sampling...")
    Xp, Xt, y, uids = build_sequences_with_sampling(
        user_orders, product_to_idx, other_token=1, all_pids=top_products,
        max_hist=MAX_ORDER_HISTORY, max_items=MAX_ITEMS_PER_ORDER,
        num_neg=NUM_NEGATIVES
    )
    print(f"Total training samples: {len(Xp)}")
    print(f"Product input shape: {Xp.shape}")   # (n_samples, 15, 10)
    print(f"Time input shape: {Xt.shape}")      # (n_samples, 15, 5)
    
    print("\n[4] Building user clusters...")
    u2c, n_clusters = get_clusters(user_orders, product_to_idx)
    print(f"Number of clusters: {n_clusters}")
    
    print("\n[5] Building model...")
    model = build_model(
        num_classes=num_classes,
        vocab_size=vocab_size,
        max_hist=MAX_ORDER_HISTORY,
        max_items=MAX_ITEMS_PER_ORDER,
        lstm_units=64,
        dropout=0.2
    )
    model.summary()
    
    # Train/validation split
    idx = np.arange(len(Xp))
    tr_idx, va_idx = train_test_split(idx, test_size=0.2, random_state=42)
    
    Xp_tr, Xp_va = Xp[tr_idx], Xp[va_idx]
    Xt_tr, Xt_va = Xt[tr_idx], Xt[va_idx]
    y_tr, y_va = y[tr_idx], y[va_idx]
    
    c_tr = np.array([[u2c.get(uids[i], 0)] for i in tr_idx], dtype=np.int32)
    c_va = np.array([[u2c.get(uids[i], 0)] for i in va_idx], dtype=np.int32)
    
    print("\n[6] Training...")
    early_stop = keras.callbacks.EarlyStopping(
        monitor='val_loss', patience=3, restore_best_weights=True
    )
    history = model.fit(
        [Xp_tr, Xt_tr, c_tr], y_tr,
        batch_size=BATCH_SIZE,
        epochs=EPOCHS,
        validation_data=([Xp_va, Xt_va, c_va], y_va),
        callbacks=[early_stop],
        verbose=1
    )
    
    print("\n" + "=" * 50)
    print("EVALUATION")
    print("=" * 50)
    
    logits = model.predict([Xp_va, Xt_va, c_va], verbose=0)
    probs = tf.nn.softmax(logits, axis=-1).numpy()
    
    # Hit rates
    hit1 = hit3 = hit5 = hit10 = 0
    total = len(y_va)
    for i, true_idx in enumerate(y_va):
        top10 = np.argsort(probs[i])[-10:]
        if true_idx in top10[-1:]:
            hit1 += 1
        if true_idx in top10[-3:]:
            hit3 += 1
        if true_idx in top10[-5:]:
            hit5 += 1
        if true_idx in top10:
            hit10 += 1
    
    print(f"\nHit Rates:")
    print(f"  @1:  {hit1/total:.4f}")
    print(f"  @3:  {hit3/total:.4f}")
    print(f"  @5:  {hit5/total:.4f}")
    print(f"  @10: {hit10/total:.4f}")
    
    # Top-K accuracy
    print(f"\nTop-K Accuracy:")
    for k in [1, 3, 5, 10]:
        acc = np.mean(np.any(np.argsort(probs, axis=1)[:, -k:] == y_va.reshape(-1, 1), axis=1))
        print(f"  Top-{k}: {acc:.4f}")
    
    # Save model and mappings
    print("\nSaving...")
    os.makedirs("ml/recommendation/final", exist_ok=True)
    model.save("ml/recommendation/final/sigmoid_v5.keras")
    with open("ml/recommendation/final/sigmoid_v5_mappings.pkl", "wb") as f:
        pickle.dump({
            "p2i": product_to_idx,
            "i2p": idx_to_product,
            "u2c": u2c,
            'max_items': MAX_ITEMS_PER_ORDER,
            'max_orders': MAX_ORDER_HISTORY,
        }, f)
    print("Done.")
    return model

if __name__ == "__main__":
    train_v5()