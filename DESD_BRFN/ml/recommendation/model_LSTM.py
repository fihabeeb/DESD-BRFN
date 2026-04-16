# ml/recommendation/new/model_LSTM_simple_db.py

import numpy as np
import tensorflow as tf
from tensorflow import keras
from collections import defaultdict
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.sequence import pad_sequences
import pickle
from orders.models import OrderItem


# Import your existing DB functions (adjust path as needed)
# Assuming these are in the same Django app
# from ml.recommendation.model_enhanced import get_user_sequences_with_timestamps, encode_products
# from ml.recommendation.model_LSTM import train_simple_lstm
# _,_,_ = train_simple_lstm(max_seq_len=7)


NUM_OF_FEATURES = 5
SEQ_LEN = 20
#
# Utility
#
def get_user_sequences_with_timestamps(ignore_quantity=True, no_limit=True):
    """
    Extract user purchase sequences with temporal information from paid orders.
    
    Returns:
        dict: {user_id: [(product_id, timestamp, order_id), ...]} ordered by time

        Key: 13, Value: [(150, datetime.datetime(2026, 3, 9, 16, 46, 39, 80576, tzinfo=datetime.timezone.utc), 103),
    """
    from datetime import datetime
    
    sequences = defaultdict(list)
    
    # Filter only paid orders with all necessary relations
    order_items = OrderItem.objects.filter(
        producer_order__payment__payment_status='paid'
    ).exclude(
        producer_order__payment__user__customer_profile__id=1
        # producer_order__payment__created_at__range=
    ).select_related(
        'product', 
        'producer_order__payment__user',
        'producer_order__payment'
    )
    
    # Sort by payment creation time (chronological order)
    order_items = order_items.order_by('producer_order__payment__created_at')
    
    for item in order_items:
        user = item.producer_order.payment.user
        product = item.product
        timestamp = item.producer_order.payment.created_at
        order_id = item.producer_order.payment.id
        
        # ignoring 
        current_order_id = None
        products_in_order = set()

        if not user or not product or not timestamp:
            continue
        
        if ignore_quantity:
            # For each order, add each product only once
            if order_id != current_order_id:
                # New order: reset the set
                current_order_id = order_id
                products_in_order.clear()
            
            if product.id not in products_in_order:
                sequences[user.id].append((product.id, timestamp, order_id))
                products_in_order.add(product.id)
        else:
        # Store tuple of (product_id, timestamp, order_id)
        # Repeat product ID based on quantity purchased
            repeat_limit = None if no_limit else 3
            for _ in range(item.quantity, repeat_limit):
                sequences[user.id].append((product.id, timestamp, order_id))
    
    return dict(sequences)


#
# encode
#
def encode_products(X, y):
    """
    Encode product IDs to sequential indices (reserving 0 for padding).
    
    Args:
        X: List of product ID sequences
        y: List of target product IDs
    
    Returns:
        tuple: (encoded_X, encoded_y, product_to_idx, idx_to_product)
    """
    # Get unique product IDs from both X and y
    all_products = set()
    for seq in X:
        all_products.update(seq)
    all_products.update(y)
    
    # Reserve 0 for padding token
    product_to_idx = {product: idx + 1 for idx, product in enumerate(sorted(all_products))}
    idx_to_product = {idx + 1: product for idx, product in enumerate(sorted(all_products))}
    
    # Add padding token mapping
    product_to_idx[0] = 0  # padding token
    idx_to_product[0] = 0  # padding token
    
    # Encode sequences
    encoded_X = [[product_to_idx[p] for p in seq] for seq in X]
    encoded_y = [product_to_idx[p] for p in y]
    
    return encoded_X, encoded_y, product_to_idx, idx_to_product


#
# Train
#
def train_simple_lstm(
    max_seq_len=SEQ_LEN,
    embedding_dim=64,
    lstm_units=128,
    user_embedding_dim=32,
    dense_nodes=32,
    batch_size=32,
    epochs=30,
    test_size=0.2,
    save_model=True,
    model_save_path="ml/recommendation/final/simple_lstm_db.keras",
    mappings_save_path="ml/recommendation/final/simple_lstm_mappings.pkl"
):
    """
    Train a simple LSTM model for next-item prediction using purchase history from DB.
    
    Args:
        max_seq_len: Number of previous purchases to look at
        embedding_dim: Size of product embedding
        lstm_units: Number of LSTM units
        dense_nodes: Size of dense layer after LSTM
        batch_size: Training batch size
        epochs: Number of training epochs
        test_size: Fraction of data to use for validation
        save_model: Whether to save the model and mappings
        model_save_path: Path to save the Keras model
        mappings_save_path: Path to save the product mappings pickle
    
    Returns:
        tuple: (model, product_to_idx, idx_to_product, history)
    """
    
    print("=" * 60)
    print("Starting simple LSTM training from database data")
    print("=" * 60)
    
    # 1. Load data from DB
    print("\n[1/6] Loading purchase sequences from database...")
    user_sequences = get_user_sequences_with_timestamps(ignore_quantity=False, no_limit=False)
    if not user_sequences:
        raise ValueError("No user sequences found in database.")
    
    
    # 2. Create sliding windows (X = context, y = next item)
    print("\n[2/6] Creating sliding window sequences...")
    X_product_raw = []
    X_time_features_raw = []

    y_product_raw = []
    user_ids_raw = []

    for user_id, seq in user_sequences.items():
        if len(seq) < 2:
            continue

        product_seq = [item[0] for item in seq]
        timestamp_seq = [item[1] for item in seq]
        days_since_last_seq = [0.0]  # first purchase has 0
        
        for i in range(1, len(timestamp_seq)):
            delta = (timestamp_seq[i] - timestamp_seq[i-1]).total_seconds() / (24*3600)  # days
            days_since_last_seq.append(delta)

        for i in range(1, len(product_seq)):
            # Context indices: from start to i-1
            start = max(0, i - max_seq_len)
            context_indices = list(range(start, i))   # positions of context items
            
            # Product context
            context_products = [product_seq[j] for j in context_indices]
            X_product_raw.append(context_products)
            
            # Temporal features context: for each position, compute feature vector
            context_features = []
            for j in context_indices:
                ts = timestamp_seq[j]
                feat = extract_temporal_features(ts)   # returns list of 5 floats
                context_features.append(feat)
            X_time_features_raw.append(context_features)
            
            # Target
            y_product_raw.append(product_seq[i])
            user_ids_raw.append(user_id)

    print(f"Created {len(X_product_raw)} training samples")
    print(f"Unique users: {len(set(user_ids_raw))}")
    
    # from collections import Counter
    
    #-------- 3. Encode product IDs to indices (0 reserved for padding)
    print("\n[3/6] Encoding product IDs...")
    X_encoded, y_encoded, product_to_idx, idx_to_product = encode_products(
        X_product_raw, y_product_raw
    )
    X_padded = pad_sequences(X_encoded, maxlen=max_seq_len, padding='pre', truncating='pre')

    # pad time features
    num_time_features = NUM_OF_FEATURES
    X_time_padded = []
    for seq in X_time_features_raw:
        if len(seq) >= max_seq_len:
            # Truncate from the left (keep last max_seq_len)
            seq = seq[-max_seq_len:]
        else:
            # Pad on the left with zero vectors
            pad_length = max_seq_len - len(seq)
            seq = [[0.0]*num_time_features for _ in range(pad_length)] + seq
        X_time_padded.append(seq)
    X_time_padded = np.array(X_time_padded, dtype=np.float32)

    y_array = np.array(y_encoded, dtype=np.int32)
    num_products = len([k for k in product_to_idx.keys() if k != 0])
    print(f"Number of unique products: {num_products}")
    print(f"Padded X shape: {X_padded.shape}")
    print(f"y shape: {y_array.shape}")

    unique_users = sorted(set(user_ids_raw))
    user_to_idx = {uid: i+1 for i, uid in enumerate(unique_users)}  # 0 for padding
    idx_to_user = {i+1: uid for uid, i in user_to_idx.items()}
    user_encoded = np.array([user_to_idx[uid] for uid in user_ids_raw], dtype=np.int32)

    num_users = len(unique_users) + 1  # +1 for padding index 0
    print(f"Number of unique users: {len(unique_users)}")
    print(f"User embedding size: {num_users}")
    

    #------------ 4. Train/test split
    print("\n[4/6] Splitting data...")
    indices = np.arange(len(X_padded))
    train_idx, val_idx = train_test_split(indices, test_size=test_size, random_state=42)

    X_train_prod = X_padded[train_idx]
    X_val_prod = X_padded[val_idx]

    X_train_time = X_time_padded[train_idx]
    X_val_time = X_time_padded[val_idx]

    y_train = y_array[train_idx]
    y_val = y_array[val_idx]

    user_train = user_encoded[train_idx].reshape(-1, 1)
    user_val = user_encoded[val_idx].reshape(-1, 1)

    train_dataset = tf.data.Dataset.from_tensor_slices((
        (X_train_prod, X_train_time, user_train), y_train
    )).shuffle(1000).batch(batch_size)

    val_dataset = tf.data.Dataset.from_tensor_slices((
        (X_val_prod, X_val_time, user_val), y_val
    )).batch(batch_size)

    #
    #
    # ------------ 5. Build model ----------------
    print("\n[5/6] Building LSTM model...")
    # Product sequence input
    
    # Product branch
    product_input = keras.Input(shape=(max_seq_len,), name='product_input')
    product_embed = keras.layers.Embedding(
        input_dim=len(product_to_idx),
        output_dim=64,
        mask_zero=True,
        name='product_embedding'
    )(product_input)

    # time branch
    time_input = keras.Input(shape=(max_seq_len, num_time_features), name = 'time_input')
    # time_dense = keras.layers.Dense(32, activation='relu')(time_input)

    combined = keras.layers.Concatenate(axis=-1)([product_embed, time_input])

    lstm_out = keras.layers.LSTM(128, dropout=0.2, return_sequence=True, name='lstm')(combined)
    lstm_out = keras.layers.LSTM(64, dropout=0.2, name='lstm')(lstm_out)


    # User ID input
    user_input = keras.Input(shape=(1,), name='user_input')
    user_embed = keras.layers.Embedding(
        input_dim=num_users,
        output_dim=user_embedding_dim,
        name='user_embedding'
    )(user_input)
    user_embed_flat = keras.layers.Flatten()(user_embed)

    # Combine
    combined = keras.layers.Concatenate()([lstm_out, user_embed_flat])

    # Additional layers
    z = keras.layers.Dense(64, activation='relu')(combined)
    z = keras.layers.BatchNormalization()(z)
    z = keras.layers.Dropout(0.2)(z)

    output = keras.layers.Dense(num_products + 1, activation='softmax', name='output')(z)

    model = keras.Model(
        inputs=[product_input, time_input, user_input],
        outputs=output
    )

    model.compile(
        optimizer='adam',
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    model.summary()

    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
    callbacks = [
        EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True,
            verbose=1
        ),
        ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=5,
            min_lr=0.00001,
            verbose=1
        ),
        ModelCheckpoint(
            'ml/recommendation/checkpoint/simple_lstm_model.keras',
            monitor='val_accuracy',
            save_best_only=True,
            verbose=1
        )
    ]

    # 7. Train
    print("\n[6/6] Training model...")
    history = model.fit(
        train_dataset,
        epochs=epochs,
        batch_size=batch_size,
        validation_data=val_dataset,
        callbacks=callbacks,
        verbose=1
    )

    # Evaluate
    val_loss, val_acc = model.evaluate(val_dataset, verbose=0)
    print(f"\nValidation Accuracy: {val_acc:.4f}")

    # Save
    if save_model:
        print(f"\nSaving model to {model_save_path}")
        model.save(model_save_path)
        mappings = {
            'product_to_idx': product_to_idx,
            'idx_to_product': idx_to_product,
            'user_to_idx': user_to_idx,
            'idx_to_user': idx_to_user,
            'max_seq_len': max_seq_len,
            'num_products': num_products,
            'num_users': num_users
        }
        with open(mappings_save_path, 'wb') as f:
            pickle.dump(mappings, f)
        print(f"Saved mappings to {mappings_save_path}")

    print("\nTraining completed!")
    return model, product_to_idx, idx_to_product, user_to_idx, idx_to_user, history


import datetime
def extract_temporal_features(timestamp: datetime.datetime, days_since_last=0):

    # day of week
    day_of_week = timestamp.weekday()
    # cylical encoding
    day_sin = np.sin(2 * np.pi * day_of_week / 7.0)
    day_cos = np.cos(2 * np.pi * day_of_week / 7.0)

    # month
    month = timestamp.month
    month_sin = np.sin(2 * np.pi * month / 12.0)
    month_cos = np.cos(2 * np.pi * month / 12.0)

    # is weekend
    is_weekend = 1.0 if day_of_week >= 5 else 0.0

    days_norm = np.log1p(days_since_last) / 6.0
    days_norm = min(days_norm, 1.0)

    return [day_sin, day_cos, month_sin, month_cos, is_weekend]





#
#
# recommend
#
def recommend_with_user(
    user_id, user_history_ids, model, product_to_idx, idx_to_product,
    user_to_idx, max_seq_len=10, top_k=5
):
    """
    Recommend next items for a specific user.
    """
    # Encode product history
    encoded_products = [product_to_idx.get(pid, 0) for pid in user_history_ids]
    if len(encoded_products) > max_seq_len:
        encoded_products = encoded_products[-max_seq_len:]
    elif len(encoded_products) < max_seq_len:
        encoded_products = [0] * (max_seq_len - len(encoded_products)) + encoded_products

    # Encode user
    encoded_user = user_to_idx.get(user_id, 0)

    # Predict
    product_input = np.array([encoded_products], dtype=np.int32)
    user_input = np.array([[encoded_user]], dtype=np.int32)
    predictions = model.predict([product_input, user_input], verbose=0)[0]

    # Get top-k (skip index 0)
    valid = [i for i in range(len(predictions)) if i != 0 and i in idx_to_product]
    top_indices = sorted(valid, key=lambda i: predictions[i], reverse=True)[:top_k]
    return [(idx_to_product[i], float(predictions[i])) for i in top_indices]


def recommend_next_items(user_history_ids, model, product_to_idx, idx_to_product, max_seq_len=5, top_k=5):
    """
    Recommend next items for a user given their purchase history.
    
    Args:
        user_history_ids: List of product IDs (actual database IDs) in chronological order
        model: Trained Keras model
        product_to_idx: Dict mapping product ID -> encoded index
        idx_to_product: Dict mapping encoded index -> product ID
        max_seq_len: Sequence length the model expects
        top_k: Number of recommendations to return
    
    Returns:
        List of tuples [(product_id, probability), ...]
    """
    # Encode history
    encoded = [product_to_idx.get(pid, 0) for pid in user_history_ids]
    
    # Pad or truncate to max_seq_len
    if len(encoded) > max_seq_len:
        encoded = encoded[-max_seq_len:]
    elif len(encoded) < max_seq_len:
        encoded = [0] * (max_seq_len - len(encoded)) + encoded
    
    input_tensor = np.array([encoded], dtype=np.int32)
    predictions = model.predict(input_tensor, verbose=0)[0]
    
    # Get top-k (skip index 0 which is padding)
    valid_indices = [i for i in range(len(predictions)) if i != 0 and i in idx_to_product]
    top_indices = sorted(valid_indices, key=lambda i: predictions[i], reverse=True)[:top_k]
    
    recommendations = [(idx_to_product[i], float(predictions[i])) for i in top_indices]
    return recommendations


def recommend_next_timeaware(user_id, user_history_with_timestamps, model, product_to_idx, idx_to_product, user_to_idx, top_k=6):
    """
    user_history_with_timestamps: list of (product_id, datetime) in chronological order
    """
    max_seq_len = SEQ_LEN

    # Encode product IDs and build time features
    encoded_products = []
    time_features = []
    for pid, ts in user_history_with_timestamps[-max_seq_len:]:  # take last max_seq_len
        encoded_products.append(product_to_idx.get(pid, 0))
        time_features.append(extract_temporal_features(ts))
    
    # Pad if needed (left pad)
    if len(encoded_products) < max_seq_len:
        pad_len = max_seq_len - len(encoded_products)
        encoded_products = [0]*pad_len + encoded_products
        time_features = [[0.0]*5 for _ in range(pad_len)] + time_features
    
    # Prepare inputs
    prod_input = np.array([encoded_products], dtype=np.int32)
    time_input = np.array([time_features], dtype=np.float32)
    user_input = np.array([[user_to_idx.get(user_id, 0)]], dtype=np.int32)
    
    predictions = model.predict([prod_input, time_input, user_input], verbose=0)[0]
    
    # Get top-k (skip 0)
    valid = [i for i in range(len(predictions)) if i != 0 and i in idx_to_product]
    top_indices = sorted(valid, key=lambda i: predictions[i], reverse=True)[:top_k]
    return [(idx_to_product[i], float(predictions[i])) for i in top_indices]

