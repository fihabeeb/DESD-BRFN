import numpy as np
import tensorflow as tf
from tensorflow import keras
from collections import defaultdict, Counter
from sklearn.model_selection import train_test_split
import pickle
import datetime
import logging

logger = logging.getLogger(__name__)

from products.models import Product, ProductCategory
from orders.models import OrderItem, OrderPayment, OrderProducer
from django.db.models import Sum, Count, Avg

# ------------------------------------------------------------
# Helper: extract temporal features (day, month, weekend)
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
# 1. Data extraction – item-level sequences (flatten orders)
# ------------------------------------------------------------
def get_user_item_sequences():
    """
    Returns a dict: user_id -> list of (product_id, category_id, timestamp)
    Each product purchased becomes one event, preserving order by timestamp.
    """
    user_items = defaultdict(list)

    order_items = OrderItem.objects.filter(
        producer_order__payment__payment_status='paid'
    ).select_related(
        'product', 'producer_order__payment__user',
        'product__category',
    ).order_by(
        'producer_order__payment__user__id',
        'producer_order__payment__created_at',
        'id',
    )

    for item in order_items:
        user = item.producer_order.payment.user
        if user is None:
            continue
        timestamp = item.producer_order.payment.created_at
        product_id = item.product.id
        category_id = item.product.category.id if item.product.category else 0

        user_items[user.id].append((product_id, category_id, timestamp))

    return dict(user_items)

# ------------------------------------------------------------
# 2. Limit to top K products (most frequent)
# ------------------------------------------------------------
def get_top_products(user_item_sequences, top_k=200):
    product_counter = Counter()
    for items in user_item_sequences.values():
        for (pid, _, _) in items:
            product_counter[pid] += 1
    top_product_ids = [pid for pid, _ in product_counter.most_common(top_k)]
    return set(top_product_ids)

# ------------------------------------------------------------
# 3. Build item-level sequences with sliding window
# ------------------------------------------------------------
def build_item_sequences(user_item_sequences, top_product_set, max_seq_len=20):
    """
    Creates training samples: context = previous max_seq_len items, target = next item.
    """
    top_list = sorted(top_product_set)
    product_to_idx = {pid: i+2 for i, pid in enumerate(top_list)}  # indices 2..len+1
    other_token = 1
    product_to_idx[0] = 0
    idx_to_product = {0: 0, other_token: None}
    for pid, idx in product_to_idx.items():
        if pid != 0:
            idx_to_product[idx] = pid
    # IMPORTANT: +2 for padding (0) and other (1)
    num_products = len(top_list) + 2

    # Category mappings
    all_categories = set()
    for items in user_item_sequences.values():
        for (_, cat_id, _) in items:
            all_categories.add(cat_id)
    category_to_idx = {cat: i+1 for i, cat in enumerate(sorted(all_categories))}
    category_to_idx[0] = 0
    num_categories = len(all_categories) + 1

    X_products = []
    X_categories = []
    X_time = []
    y_product = []
    y_category = []

    for user_id, items in user_item_sequences.items():
        if len(items) < 2:
            continue
        for i in range(1, len(items)):
            context_items = items[:i]
            target_item = items[i]

            prod_seq = [product_to_idx.get(pid, other_token) for (pid, _, _) in context_items]
            cat_seq = [category_to_idx.get(cat, 0) for (_, cat, _) in context_items]
            time_seq = [extract_temporal_features(ts) for (_, _, ts) in context_items]

            if len(prod_seq) > max_seq_len:
                prod_seq = prod_seq[-max_seq_len:]
                cat_seq = cat_seq[-max_seq_len:]
                time_seq = time_seq[-max_seq_len:]

            pad_len = max_seq_len - len(prod_seq)
            if pad_len > 0:
                prod_seq = [0] * pad_len + prod_seq
                cat_seq = [0] * pad_len + cat_seq
                time_seq = [[0.0]*5] * pad_len + time_seq

            target_pid = target_item[0]
            target_cat = target_item[1]
            y_product.append(product_to_idx.get(target_pid, other_token))
            y_category.append(category_to_idx.get(target_cat, 0))

            X_products.append(prod_seq)
            X_categories.append(cat_seq)
            X_time.append(time_seq)

    return (np.array(X_products, dtype=np.int32),
            np.array(X_categories, dtype=np.int32),
            np.array(X_time, dtype=np.float32),
            np.array(y_product, dtype=np.int32),
            np.array(y_category, dtype=np.int32),
            product_to_idx, idx_to_product,
            category_to_idx,
            num_products, num_categories,
            other_token)

# ------------------------------------------------------------
# 4. Encode users
# ------------------------------------------------------------
def encode_users_from_sequences(user_item_sequences, X_products, original_users):
    unique_users = sorted(set(original_users))
    user_to_idx = {uid: i+1 for i, uid in enumerate(unique_users)}
    user_to_idx[0] = 0
    idx_to_user = {i+1: uid for i, uid in enumerate(unique_users)}
    idx_to_user[0] = 0
    num_users = len(unique_users) + 1
    user_encoded = np.array([user_to_idx[uid] for uid in original_users], dtype=np.int32).reshape(-1, 1)
    return user_encoded, user_to_idx, idx_to_user, num_users

# ------------------------------------------------------------
# 5. Model definition with Attention and multi-task learning
# ------------------------------------------------------------
def build_lstm_attention_model(max_seq_len, num_products, num_categories, num_users,
                               embedding_dim=64, lstm_units=128):
    """
    Multi‑task LSTM with attention:
    Inputs: product ids, category ids, time features, user id
    Outputs: next product (softmax), next category (softmax)
    """
    prod_input = keras.Input(shape=(max_seq_len,), name='product_input')
    cat_input = keras.Input(shape=(max_seq_len,), name='category_input')
    time_input = keras.Input(shape=(max_seq_len, 5), name='time_input')
    user_input = keras.Input(shape=(1,), name='user_input')

    prod_embed = keras.layers.Embedding(num_products, embedding_dim, mask_zero=True, name='prod_emb')(prod_input)
    cat_embed = keras.layers.Embedding(num_categories, 16, mask_zero=True, name='cat_emb')(cat_input)

    combined = keras.layers.Concatenate(axis=-1)([prod_embed, cat_embed, time_input])

    lstm_out = keras.layers.LSTM(lstm_units, return_sequences=True, name='lstm')(combined)

    # Self-attention
    attention = keras.layers.Attention(name='attention')([lstm_out, lstm_out])
    context = keras.layers.GlobalAveragePooling1D()(attention)

    user_embed = keras.layers.Embedding(num_users, 16, name='user_emb')(user_input)
    user_flat = keras.layers.Flatten()(user_embed)

    merged = keras.layers.Concatenate()([context, user_flat])
    dense = keras.layers.Dense(64, activation='relu')(merged)
    dropout = keras.layers.Dropout(0.2)(dense)

    prod_output = keras.layers.Dense(num_products, activation='softmax', name='product_output')(dropout)
    cat_output = keras.layers.Dense(num_categories, activation='softmax', name='category_output')(dropout)

    model = keras.Model(
        inputs=[prod_input, cat_input, time_input, user_input],
        outputs=[prod_output, cat_output]
    )

    model.compile(
        optimizer='adam',
        loss={
            'product_output': 'sparse_categorical_crossentropy',
            'category_output': 'sparse_categorical_crossentropy',
        },
        loss_weights={'product_output': 1.0, 'category_output': 0.5},
        metrics={'product_output': ['accuracy'], 'category_output': ['accuracy']}
    )
    return model

# ------------------------------------------------------------
# 6. Main training function
# ------------------------------------------------------------
def train_lstm_attention(
    max_seq_len=30,
    batch_size=64,
    epochs=20,
    test_size=0.2,
    top_k_products=100,
    save_model=True,
    model_save_path="ml/recommendation/final/lstm_attention.keras",
    mappings_save_path="ml/recommendation/final/attention_mappings.pkl"
):
    print("=" * 60)
    print("Training LSTM + Attention (item-level, multi-task)")
    print("=" * 60)

    print("\n[1/6] Loading user item sequences...")
    user_sequences = get_user_item_sequences()
    if not user_sequences:
        raise ValueError("No user item sequences found.")

    print(f"\n[2/6] Selecting top {top_k_products} products...")
    top_products = get_top_products(user_sequences, top_k=top_k_products)
    print(f"Selected {len(top_products)} products (plus 'other' token)")

    print("\n[3/6] Building sliding window samples...")
    (X_prod, X_cat, X_time,
     y_prod, y_cat,
     product_to_idx, idx_to_product,
     category_to_idx,
     num_products, num_categories,
     other_token) = build_item_sequences(user_sequences, top_products, max_seq_len)

    print(f"Total samples: {len(X_prod)}")
    print(f"Unique products in output: {num_products-1} (plus other)")

    # Build user list parallel to samples
    user_ids_for_samples = []
    for uid, items in user_sequences.items():
        for i in range(1, len(items)):
            user_ids_for_samples.append(uid)
    assert len(user_ids_for_samples) == len(X_prod)

    user_encoded, user_to_idx, idx_to_user, num_users = encode_users_from_sequences(
        user_sequences, X_prod, user_ids_for_samples
    )

    print("\n[4/6] Splitting data...")
    indices = np.arange(len(X_prod))
    train_idx, val_idx = train_test_split(indices, test_size=test_size, random_state=42)

    X_prod_train = X_prod[train_idx]
    X_cat_train = X_cat[train_idx]
    X_time_train = X_time[train_idx]
    user_train = user_encoded[train_idx]
    y_prod_train = y_prod[train_idx]
    y_cat_train = y_cat[train_idx]

    X_prod_val = X_prod[val_idx]
    X_cat_val = X_cat[val_idx]
    X_time_val = X_time[val_idx]
    user_val = user_encoded[val_idx]
    y_prod_val = y_prod[val_idx]
    y_cat_val = y_cat[val_idx]

    print("\n[5/6] Building LSTM + Attention model...")
    model = build_lstm_attention_model(
        max_seq_len, num_products, num_categories, num_users,
        embedding_dim=64, lstm_units=128
    )
    model.summary()

    callbacks = [
        keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True, verbose=1),
        keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=3, verbose=1),
        keras.callbacks.ModelCheckpoint('ml/recommendation/final/checkpoint/lstm_att.keras', monitor='val_loss', save_best_only=True)
    ]

    print("\n[6/6] Training...")
    history = model.fit(
        [X_prod_train, X_cat_train, X_time_train, user_train],
        {'product_output': y_prod_train, 'category_output': y_cat_train},
        batch_size=batch_size,
        epochs=epochs,
        validation_data=(
            [X_prod_val, X_cat_val, X_time_val, user_val],
            {'product_output': y_prod_val, 'category_output': y_cat_val}
        ),
        callbacks=callbacks,
        verbose=1
    )

    # Evaluate
    eval_results = model.evaluate(
        [X_prod_val, X_cat_val, X_time_val, user_val],
        {'product_output': y_prod_val, 'category_output': y_cat_val},
        verbose=0
    )
    # eval_results = [loss, prod_loss, cat_loss, prod_acc, cat_acc]
    val_loss = eval_results[0]
    val_prod_acc = eval_results[3]
    val_cat_acc = eval_results[4]
    print(f"\nValidation: loss={val_loss:.4f}, product_acc={val_prod_acc:.4f}, category_acc={val_cat_acc:.4f}")

    if save_model:
        print(f"Saving model to {model_save_path}")
        model.save(model_save_path)
        mappings = {
            'product_to_idx': product_to_idx,
            'idx_to_product': idx_to_product,
            'category_to_idx': category_to_idx,
            'user_to_idx': user_to_idx,
            'idx_to_user': idx_to_user,
            'max_seq_len': max_seq_len,
            'num_products': num_products,
            'num_categories': num_categories,
            'other_token': other_token,
            'top_k_products': top_k_products
        }
        with open(mappings_save_path, 'wb') as f:
            pickle.dump(mappings, f)
        print("Mappings saved.")

    return model, product_to_idx, idx_to_product, user_to_idx, idx_to_user, history

# ------------------------------------------------------------
# 7. Recommendation function
# ------------------------------------------------------------
def recommend_next_items_lstm_attention(
    user_id, user_history_products, user_history_categories, user_history_timestamps,
    model, product_to_idx, idx_to_product, category_to_idx, user_to_idx,
    max_seq_len=20, top_k=5, other_token=1
):
    """
    user_history_* are lists of the user's past purchases (each element is one item).
    Returns list of (product_id, probability).
    """
    # Truncate
    if len(user_history_products) > max_seq_len:
        user_history_products = user_history_products[-max_seq_len:]
        user_history_categories = user_history_categories[-max_seq_len:]
        user_history_timestamps = user_history_timestamps[-max_seq_len:]

    # Pad left
    pad_len = max_seq_len - len(user_history_products)
    if pad_len > 0:
        user_history_products = [0] * pad_len + user_history_products
        user_history_categories = [0] * pad_len + user_history_categories
        zero_feat = [0.0] * 5
        user_history_timestamps = [zero_feat] * pad_len + user_history_timestamps

    # Encode
    encoded_prods = [product_to_idx.get(p, other_token) if p != 0 else 0 for p in user_history_products]
    encoded_cats = [category_to_idx.get(c, 0) for c in user_history_categories]
    time_feats = [extract_temporal_features(ts) if isinstance(ts, datetime.datetime) else ts for ts in user_history_timestamps]

    prod_input = np.array([encoded_prods], dtype=np.int32)
    cat_input = np.array([encoded_cats], dtype=np.int32)
    time_input = np.array([time_feats], dtype=np.float32)
    user_enc = user_to_idx.get(user_id, 0)
    user_input = np.array([[user_enc]], dtype=np.int32)

    pred_probs, _ = model.predict([prod_input, cat_input, time_input, user_input], verbose=0)
    pred_probs = pred_probs[0]  # shape (num_products,)

    valid_indices = [i for i in range(len(pred_probs)) if i not in (0, other_token) and i in idx_to_product]
    top_indices = sorted(valid_indices, key=lambda i: pred_probs[i], reverse=True)[:top_k]

    recommendations = [(idx_to_product[i], float(pred_probs[i])) for i in top_indices]
    return recommendations

# ------------------------------------------------------------
# 8. Cold-start helper: recommend by category
# ------------------------------------------------------------
def cold_start_by_category(category_id, top_k=5):
    """Return top_k product IDs from the given category, ordered by sales count."""
    from products.models import Product
    products = Product.objects.filter(category_id=category_id).order_by('-sales_count')[:top_k]
    return [p.id for p in products]

