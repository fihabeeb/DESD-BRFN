"""
Sigmoid model v5.1 - LSTM + Attention.

Approach:
- Use LSTM to model order sequence
- Dot-product attention to focus on relevant past orders
- Keep 15 order history, 5 items per order
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
LEARNING_RATE = 1e-3
MAX_ORDER_HISTORY = 15
MAX_ITEMS_PER_ORDER = 5
VOCAB_SIZE = 162
NUM_NEGATIVES = 20
NUM_CLASSES = 160
DROPOUT = 0.2


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
    order_items = OrderItem.objects.filter(
        producer_order__payment__payment_status="paid"
    ).exclude(
        producer_order__payment__user__customer_profile__id__range=(1,5)
    ).select_related("product", "producer_order__payment__user"
    ).order_by("producer_order__payment__created_at")
    
    current_user, current_order, products = None, None, []
    for item in order_items:
        user = item.producer_order.payment.user
        order_id = item.producer_order.payment.id
        timestamp = item.producer_order.payment.created_at
        product_id = item.product.id
        if user is None: continue
        if current_user != user.id:
            current_user, current_order, products = user.id, None, []
        if current_order != order_id:
            if current_order and products:
                user_orders[current_user].append((current_order, timestamp, list(set(products))))
            current_order, products = order_id, [product_id]
        else:
            if product_id not in products: products.append(product_id)
    if current_user and current_order and products:
        user_orders[current_user].append((current_order, timestamp, products))
    return dict(user_orders)


def build_sequences_with_sampling(user_orders, product_to_idx, other_token, all_pids,
                              max_hist=15, max_items=5, num_neg=20, seed=42):
    np.random.seed(seed)
    X_prod, X_time, y_labels, user_ids = [], [], [], []
    all_pids = list(all_pids)
    
    for uid, orders in user_orders.items():
        if len(orders) < 2: continue
        for i in range(len(orders) - 1):
            ctx = orders[:i+1]; tgt = orders[i+1]
            ctx_prods, ctx_times = [], []
            for _, ts, ps in ctx[-max_hist:]:
                ps = ps[:max_items]
                if len(ps) < max_items: ps = ps + [0] * (max_items - len(ps))
                enc = [product_to_idx.get(p, other_token) if p != 0 else 0 for p in ps]
                ctx_prods.append(enc); ctx_times.append(extract_temporal_features(ts))
            while len(ctx_prods) < max_hist:
                ctx_prods = [[0]*max_items] + ctx_prods
                ctx_times = [[0.0]*5] + ctx_times
            
            pos_idx = [product_to_idx.get(p, other_token) for p in tgt[2] if p in product_to_idx]
            pos_idx = [p for p in pos_idx if p >= 2]
            if not pos_idx: continue
            
            neg_pool = [p for p in all_pids if p not in tgt[2]]
            if len(neg_pool) >= num_neg:
                negs = np.random.choice(neg_pool, num_neg, replace=False)
            else:
                negs = neg_pool
            neg_idx = [product_to_idx.get(p, other_token) for p in negs if p in product_to_idx]
            neg_idx = [p for p in neg_idx if p >= 2][:num_neg]
            
            for pidx in pos_idx:
                X_prod.append(ctx_prods)
                X_time.append(ctx_times)
                y_labels.append(pidx)
                user_ids.append(uid)
    
    return (np.array(X_prod, dtype=np.int32), np.array(X_time, dtype=np.float32),
            np.array(y_labels, dtype=np.int32), user_ids)


def build_model(num_classes=160, seq_len=15, items_per_order=5, 
                vocab_size=162, lstm_units=64, n_clusters=8, dropout=0.2):
    product_ids = keras.Input(shape=(seq_len, items_per_order,), name="product_input")
    temporal = keras.Input(shape=(seq_len, 5), name="time_input")
    user_cluster = keras.Input(shape=(1,), name="user_cluster")
    
    emb = layers.Embedding(vocab_size, 32, mask_zero=True)(product_ids)
    flat_emb = layers.Reshape((seq_len, items_per_order * 32))(emb)
    
    combined = layers.Concatenate()([flat_emb, temporal])
    
    lstm_out = layers.LSTM(lstm_units, return_sequences=True)(combined)
    lstm_out = layers.Dropout(dropout)(lstm_out)
    
    last_hidden = layers.Reshape((1, lstm_units))(lstm_out[:, -1, :])
    
    attn_scores = layers.Dot(axes=(2, 2))([last_hidden, lstm_out])
    attn_weights = layers.Softmax()(attn_scores)
    attn_weights_squeezed = layers.Reshape((seq_len,))(attn_weights)
    context = layers.Dot(axes=(1, 1))([attn_weights_squeezed, lstm_out])
    context = layers.Dropout(dropout)(context)
    
    c_emb = layers.Embedding(n_clusters + 1, 8)(user_cluster)
    
    merged = layers.Concatenate()([context, layers.Flatten()(c_emb)])
    
    x = layers.Dense(64, activation="relu")(merged)
    x = layers.Dropout(dropout)(x)
    x = layers.Dense(32, activation="relu")(x)
    x = layers.Dropout(dropout * 0.5)(x)
    
    logits = layers.Dense(num_classes + 2, activation=None, name="output")(x)
    
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
        for _, _, ps in orders: cnt.update(ps)
        arr = np.zeros(max(product_to_idx.values()) + 1, dtype=np.float32)
        for p, c in cnt.items():
            i = product_to_idx.get(p)
            if i and i < len(arr): arr[i] = c
        if arr.sum() > 0: arr = arr / arr.sum()
        features[uid] = arr
    
    if len(features) < n_clusters:
        return {u: 0 for u in features}, 1
    
    X = np.array(list(features.values()))
    km = KMeans(min(n_clusters, len(X)), random_state=42, n_init=3)
    labels = km.fit_predict(X)
    return {u: labels[i] for i, u in enumerate(sorted(features.keys()))}, len(set(labels))


def train_v5_1():
    print("=" * 50)
    print("V5.1: LSTM + Attention")
    print("=" * 50)
    
    print("\n[1] Loading orders...")
    user_orders = get_user_orders()
    print(f"Users: {len(user_orders)}")
    
    print("\n[2] Building mappings...")
    counter = Counter()
    for os in user_orders.values():
        for _, _, ps in os: counter.update(ps)
    top = {p for p, _ in counter.most_common(160)}
    p2i = {p: i+2 for i, p in enumerate(sorted(top))}
    p2i[0] = 0
    i2p = {i+2: p for i, p in enumerate(sorted(top))}
    
    print("\n[3] Building sequences...")
    Xp, Xt, y, uids = build_sequences_with_sampling(
        user_orders, p2i, 1, top, MAX_ORDER_HISTORY, MAX_ITEMS_PER_ORDER, NUM_NEGATIVES
    )
    print(f"Samples: {len(Xp)}")
    print(f"Product IDs shape: {Xp.shape}")
    print(f"Temporal shape: {Xt.shape}")
    
    print("\n[4] Building clusters...")
    u2c, n_c = get_clusters(user_orders, p2i)
    print(f"Clusters: {n_c}")
    
    model = build_model(160, MAX_ORDER_HISTORY, MAX_ITEMS_PER_ORDER, VOCAB_SIZE, 64, n_c, DROPOUT)
    model.summary()
    
    idx = np.arange(len(Xp))
    tr_idx, va_idx = train_test_split(idx, test_size=0.2, random_state=42)
    
    Xp_tr, Xp_va = Xp[tr_idx], Xp[va_idx]
    Xt_tr, Xt_va = Xt[tr_idx], Xt[va_idx]
    y_tr, y_va = y[tr_idx], y[va_idx]
    c_tr = np.array([[u2c.get(uids[i], 0) for i in tr_idx]]).T
    c_va = np.array([[u2c.get(uids[i], 0) for i in va_idx]]).T
    
    print("\n[5] Training LSTM + Attention...")
    model.fit([Xp_tr, Xt_tr, c_tr], y_tr,
            batch_size=BATCH_SIZE, epochs=EPOCHS,
            validation_data=([Xp_va, Xt_va, c_va], y_va),
            callbacks=[keras.callbacks.EarlyStopping(
                "val_loss", 
                patience=5, 
                min_delta=0.01,
                restore_best_weights=True
            )],
            verbose=1)
    
    print("\n" + "=" * 50)
    print("EVALUATION")
    print("=" * 50)
    
    logits = model.predict([Xp_va, Xt_va, c_va], verbose=0)
    probs = tf.nn.softmax(logits, axis=-1).numpy()
    
    hit1 = hit3 = hit5 = hit10 = 0
    total = len(y_va)
    
    for i, true_idx in enumerate(y_va):
        top_k = np.argsort(probs[i])[-10:]
        if true_idx in top_k[-1:]: hit1 += 1
        if true_idx in top_k[-3:]: hit3 += 1
        if true_idx in top_k[-5:]: hit5 += 1
        if true_idx in top_k: hit10 += 1
    
    print(f"\nHit Rates:")
    print(f"  @1:  {hit1/total:.4f}")
    print(f"  @3:  {hit3/total:.4f}")
    print(f"  @5:  {hit5/total:.4f}")
    print(f"  @10: {hit10/total:.4f}")
    
    print(f"\nTop-K Accuracy:")
    for k in [1, 3, 5, 10]:
        acc = np.mean(np.any(np.argsort(probs, axis=1)[:, -k:] == y_va.reshape(-1, 1), axis=1))
        print(f"  Top-{k}: {acc:.4f}")
    
    if True:
        print("\nSaving...")
        model.save("ml/recommendation/final/sigmoid_v5_1.keras")
        with open("ml/recommendation/final/sigmoid_v5_1_mappings.pkl", "wb") as f:
            pickle.dump({"p2i": p2i, "i2p": i2p, "u2c": u2c}, f)
    return model


if __name__ == "__main__":
    train_v5_1()