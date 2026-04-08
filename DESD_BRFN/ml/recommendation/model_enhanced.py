# ml/recommendation/model.py

from collections import defaultdict
from orders.models import OrderItem
import numpy as np
import pickle
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Embedding, Dropout, BatchNormalization, Bidirectional
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
from sklearn.model_selection import train_test_split
import tensorflow as tf

def get_user_sequences_with_timestamps():
    """
    Extract user purchase sequences with temporal information from paid orders.
    
    Returns:
        dict: {user_id: [(product_id, timestamp, order_id), ...]} ordered by time
    """
    from datetime import datetime
    
    sequences = defaultdict(list)
    
    # Filter only paid orders with all necessary relations
    order_items = OrderItem.objects.filter(
        producer_order__payment__payment_status='paid'
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
        
        if not user or not product or not timestamp:
            continue
        
        # Store tuple of (product_id, timestamp, order_id)
        # Repeat product ID based on quantity purchased
        for _ in range(item.quantity):
            sequences[user.id].append((product.id, timestamp, order_id))
    
    return dict(sequences)


def build_training_data_with_features(sequence_length=3, min_user_sequences=2):
    """
    Create sequences with both product IDs and temporal features for training.
    
    Args:
        sequence_length: Number of previous items to use for prediction
        min_user_sequences: Minimum sequences per user to include
    
    Returns:
        tuple: (X_products, X_time_features, y_products, metadata)
    """
    user_sequences = get_user_sequences_with_timestamps()
    
    X_products = []      # Product ID sequences
    X_time_features = [] # Temporal features for each position
    y_products = []      # Target product IDs
    user_ids = []        # Track which user each sequence belongs to
    user_counts = []
    
    for user_id, seq in user_sequences.items():
        if len(seq) <= sequence_length:
            continue
        
        # Track how many sequences per user
        num_sequences = len(seq) - sequence_length
        user_counts.append(num_sequences)
        
        # Create sliding windows
        for i in range(num_sequences):
            # Extract product sequence
            product_seq = [item[0] for item in seq[i:i + sequence_length]]
            X_products.append(product_seq)
            
            # Extract temporal features for the input sequence
            time_features_seq = []
            for j in range(i, i + sequence_length):
                timestamp = seq[j][1]
                order_id = seq[j][2]
                
                # Calculate time since previous purchase (if not first item)
                if j > 0:
                    prev_timestamp = seq[j-1][1]
                    time_diff = (timestamp - prev_timestamp).total_seconds() / 3600  # Hours
                else:
                    time_diff = 0  # First purchase in sequence
                
                # Extract temporal features
                features = extract_temporal_features(timestamp, time_diff, order_id)
                time_features_seq.append(features)
            
            X_time_features.append(time_features_seq)
            
            # Target product
            y_products.append(seq[i + sequence_length][0])
            user_ids.append(user_id)
    
    # Print statistics
    if user_counts:
        print(f"Users with sufficient data: {len(user_counts)}")
        print(f"Average sequences per user: {np.mean(user_counts):.2f}")
        print(f"Total training sequences: {len(X_products)}")
    
    # Convert to numpy arrays
    X_products = np.array(X_products, dtype=np.int32)
    X_time_features = np.array(X_time_features, dtype=np.float32)
    y_products = np.array(y_products, dtype=np.int32)
    user_ids = np.array(user_ids, dtype=np.int32)
    
    metadata = {
        'user_ids': user_ids,
        'time_features_shape': X_time_features.shape,
        'num_features': X_time_features.shape[-1]
    }
    
    return X_products, X_time_features, y_products, metadata


# ml/recommendation/model.py

def extract_temporal_features(timestamp, hours_since_last_purchase, order_id):
    """
    Extract rich temporal features from a timestamp.
    
    Args:
        timestamp: datetime object
        hours_since_last_purchase: float, hours since previous purchase
        order_id: ID of the order (for grouping items in same basket)
    
    Returns:
        list: Normalized temporal features (always 13 features)
    """
    from datetime import time
    import calendar
    
    try:
        features = []
        
        # 1. Day of week (0-6, normalized to 0-1)
        day_of_week = timestamp.weekday() / 6.0
        features.append(float(day_of_week))
        
        # 2. Is weekend? (binary)
        is_weekend = 1.0 if timestamp.weekday() >= 5 else 0.0
        features.append(float(is_weekend))
        
        # 3. Hour of day (0-23, normalized)
        hour_of_day = timestamp.hour / 23.0
        features.append(float(hour_of_day))
        
        # 4. Time of day category (morning, afternoon, evening, night)
        hour = timestamp.hour
        time_categories = [
            1.0 if 5 <= hour < 12 else 0.0,   # Morning (5-11)
            1.0 if 12 <= hour < 17 else 0.0,  # Afternoon (12-16)
            1.0 if 17 <= hour < 22 else 0.0,  # Evening (17-21)
            1.0 if hour >= 22 or hour < 5 else 0.0  # Night (22-4)
        ]
        features.extend([float(x) for x in time_categories])
        
        # 5. Day of month (1-31, normalized)
        day_of_month = timestamp.day / 31.0
        features.append(float(day_of_month))
        
        # 6. Month of year (1-12, normalized)
        month_of_year = timestamp.month / 12.0
        features.append(float(month_of_year))
        
        # 7. Is beginning of month? (first week)
        is_month_start = 1.0 if timestamp.day <= 7 else 0.0
        features.append(float(is_month_start))
        
        # 8. Is end of month? (last week)
        days_in_month = calendar.monthrange(timestamp.year, timestamp.month)[1]
        is_month_end = 1.0 if timestamp.day >= days_in_month - 7 else 0.0
        features.append(float(is_month_end))
        
        # 9. Time since last purchase (hours, log-normalized)
        if hours_since_last_purchase > 0:
            log_hours = np.log1p(hours_since_last_purchase) / 10.0
            features.append(float(min(log_hours, 1.0)))
        else:
            features.append(0.0)
        
        # 10. Same day as previous? (binary)
        same_day = 1.0 if hours_since_last_purchase < 24 else 0.0
        features.append(float(same_day))
        
        # 11. Same hour as previous? (binary)
        same_hour = 1.0 if hours_since_last_purchase < 1 else 0.0
        features.append(float(same_hour))
        
        # 12. Season (normalized)
        month = timestamp.month
        if month in [12, 1, 2]:
            season = 0.0  # Winter
        elif month in [3, 4, 5]:
            season = 0.33  # Spring
        elif month in [6, 7, 8]:
            season = 0.66  # Summer
        else:
            season = 1.0  # Fall
        features.append(float(season))
        
        # 13. Quarter of month (1st, 2nd, 3rd, 4th week)
        week_of_month = ((timestamp.day - 1) // 7) / 3.0
        features.append(float(min(week_of_month, 1.0)))
        
        # Verify we have exactly 13 features
        assert len(features) == 13, f"Expected 13 features, got {len(features)}"
        
        return features
        
    except Exception as e:
        # Return zeros if anything fails
        return [0.0] * 13

# ml/recommendation/model.py

def build_enhanced_lstm_model(num_products, sequence_length, num_time_features, 
                             num_users=None, embedding_dim=64, lstm_units=128):
    """
    Build LSTM model with both product sequences and temporal features.
    
    Args:
        num_products: Total number of unique products
        sequence_length: Length of input sequences
        num_time_features: Number of temporal features per timestep
        num_users: Total number of users (for user embedding)
        embedding_dim: Dimension of embedding layer
        lstm_units: Number of LSTM units
    
    Returns:
        tensorflow.keras.Model: Compiled model
    """
    from tensorflow.keras.layers import Input, Concatenate
    from tensorflow.keras.models import Model
    
    # Input 1: Product sequences
    product_input = Input(shape=(sequence_length,), name='product_input')
    
    # Input 2: Temporal features
    time_input = Input(shape=(sequence_length, num_time_features), name='time_input')
    
    # Optional: User ID input for user embedding
    if num_users:
        user_input = Input(shape=(1,), name='user_input')
        user_embedding = Embedding(num_users + 1, 32, name='user_embedding')(user_input)
        user_embedding = tf.keras.layers.Flatten()(user_embedding)
    
    # Product embedding
    product_embedding = Embedding(
        input_dim=num_products + 1,
        output_dim=embedding_dim,
        mask_zero=True,
        name='product_embedding'
    )(product_input)
    
    # Concatenate product embeddings with temporal features
    combined_input = Concatenate(axis=-1, name='combined_input')(
        [product_embedding, time_input]
    )
    
    # LSTM layers
    lstm_out = LSTM(lstm_units, return_sequences=True, dropout=0.2, 
                    recurrent_dropout=0.2, name='lstm_1')(combined_input)
    lstm_out = BatchNormalization(name='bn_1')(lstm_out)
    lstm_out = Dropout(0.3, name='dropout_1')(lstm_out)
    
    lstm_out = LSTM(lstm_units // 2, return_sequences=False, dropout=0.2,
                    recurrent_dropout=0.2, name='lstm_2')(lstm_out)
    lstm_out = BatchNormalization(name='bn_2')(lstm_out)
    lstm_out = Dropout(0.3, name='dropout_2')(lstm_out)
    
    # Dense layers
    dense_out = Dense(128, activation='relu', name='dense_1')(lstm_out)
    dense_out = BatchNormalization(name='bn_3')(dense_out)
    dense_out = Dropout(0.3, name='dropout_3')(dense_out)
    
    dense_out = Dense(64, activation='relu', name='dense_2')(dense_out)
    dense_out = Dropout(0.2, name='dropout_4')(dense_out)
    
    # Combine with user embedding if available
    if num_users:
        combined_features = Concatenate(name='final_features')([dense_out, user_embedding])
    else:
        combined_features = dense_out
    
    # Output layer
    output = Dense(num_products + 1, activation='softmax', name='output')(combined_features)
    
    # Create model
    if num_users:
        model = Model(inputs=[product_input, time_input, user_input], outputs=output)
    else:
        model = Model(inputs=[product_input, time_input], outputs=output)
    
    # Compile
    model.compile(
        loss='sparse_categorical_crossentropy',
        optimizer=Adam(learning_rate=0.0005),
        metrics=['accuracy']
    )
    
    return model

# ml/recommendation/model.py

# ml/recommendation/model.py

def train_enhanced_model(sequence_length=3, epochs=50, batch_size=64, validation_split=0.2):
    """
    Complete training pipeline with temporal features.
    """
    print("Step 1: Building training data with temporal features...")
    X_products, X_time_features, y_products, metadata = build_training_data_with_features(sequence_length)
    
    if len(X_products) == 0:
        raise ValueError("No training data available.")
    
    print(f"Product sequences shape: {X_products.shape}")
    print(f"Time features shape: {X_time_features.shape}")
    print(f"Number of temporal features: {metadata['num_features']}")
    
    print("Step 2: Encoding products...")
    X_enc, y_enc, p2i, i2p = encode_products(X_products.tolist(), y_products.tolist())
    num_unique_products = len([k for k in p2i.keys() if k != 0])
    
    # Convert to numpy
    X_padded = pad_sequences(X_enc, maxlen=sequence_length, padding='pre', truncating='pre')
    X_padded = np.array(X_padded, dtype=np.int32)
    y_enc = np.array(y_enc, dtype=np.int32)
    
    print("Step 3: Splitting data...")
    # Split all arrays consistently
    indices = np.arange(len(X_padded))
    train_idx, val_idx = train_test_split(indices, test_size=validation_split, random_state=42)
    
    X_train_prod = X_padded[train_idx]
    X_val_prod = X_padded[val_idx]
    X_train_time = X_time_features[train_idx]
    X_val_time = X_time_features[val_idx]
    y_train = y_enc[train_idx]
    y_val = y_enc[val_idx]
    
    # ============================================
    # FIX: Properly encode user IDs for embedding
    # ============================================
    use_user_embeddings = True  # Set to False to disable user embeddings
    
    if use_user_embeddings:
        # Get raw user IDs
        raw_user_ids = metadata['user_ids']
        
        # Create mapping from actual user ID to sequential index
        unique_users = sorted(set(raw_user_ids))
        user_to_idx = {user_id: idx + 1 for idx, user_id in enumerate(unique_users)}  # +1 to reserve 0 for padding/unknown
        idx_to_user = {idx + 1: user_id for idx, user_id in enumerate(unique_users)}
        
        # Encode user IDs
        encoded_user_ids = np.array([user_to_idx.get(uid, 0) for uid in raw_user_ids], dtype=np.int32)
        
        # Split user IDs
        X_train_user = encoded_user_ids[train_idx].reshape(-1, 1)
        X_val_user = encoded_user_ids[val_idx].reshape(-1, 1)
        
        # Number of users = number of unique users + 1 (for padding/unknown token)
        num_users = len(unique_users) + 1
        print(f"Number of unique users: {len(unique_users)}")
        print(f"User embedding size: {num_users}")
        
        # Store user mappings for later use
        user_mappings = {
            'user_to_idx': user_to_idx,
            'idx_to_user': idx_to_user,
            'num_users': num_users
        }
    else:
        num_users = None
        user_mappings = None
    
    print(f"Training samples: {len(train_idx)}")
    print(f"Validation samples: {len(val_idx)}")
    
    print("Step 4: Building enhanced model...")
    model = build_enhanced_lstm_model(
        num_products=num_unique_products,
        sequence_length=sequence_length,
        num_time_features=metadata['num_features'],
        num_users=num_users,  # Use encoded number of users
        embedding_dim=64,
        lstm_units=128
    )
    model.summary()
    
    # Callbacks
    callbacks = [
        EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=0.00001),
        ModelCheckpoint('ml/recommendation/checkpoint/rec_enhanced_best.keras', 
                       monitor='val_accuracy', save_best_only=True)
    ]
    
    print("Step 5: Training model...")
    # Prepare inputs based on whether user embeddings are used
    if num_users:
        train_inputs = [X_train_prod, X_train_time, X_train_user]
        val_inputs = [X_val_prod, X_val_time, X_val_user]
    else:
        train_inputs = [X_train_prod, X_train_time]
        val_inputs = [X_val_prod, X_val_time]
    
    history = model.fit(
        train_inputs,
        y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_data=(val_inputs, y_val),
        callbacks=callbacks,
        verbose=1
    )
    
    print("Step 6: Saving model and mappings...")
    model.save("ml/recommendation/final/recommendation_model_enhanced.keras")
    
    mappings = {
        "product_to_idx": p2i,
        "idx_to_product": i2p,
        "sequence_length": sequence_length,
        "num_products": num_unique_products,
        "num_time_features": metadata['num_features'],
        "num_users": num_users
    }
    
    # Add user mappings if they exist
    if user_mappings:
        mappings.update(user_mappings)
    
    with open("ml/recommendation/product_mappings_enhanced.pkl", "wb") as f:
        pickle.dump(mappings, f)
    
    print("\n" + "="*50)
    print("TRAINING SUMMARY")
    print("="*50)
    print(f"Final training accuracy: {history.history['accuracy'][-1]:.4f}")
    print(f"Final validation accuracy: {history.history['val_accuracy'][-1]:.4f}")
    print(f"Best validation accuracy: {max(history.history['val_accuracy']):.4f}")
    
    return model, mappings, history

# ml/recommendation/model.py

# ml/recommendation/model.py

def recommend_next_products_enhanced(model, product_to_idx, idx_to_product,
                                    purchase_history, purchase_timestamps,
                                    user_id=None, user_to_idx=None,
                                    top_k=5):
    """
    Recommend next products with temporal features and user context.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if isinstance(model.input_shape, list):
    # For multi-input models, get sequence length from the first input (product sequence)
        sequence_length = model.input_shape[0][1]
    else:
        sequence_length = model.input_shape[1]
    
    # Ensure we have matching history and timestamps
    if len(purchase_history) != len(purchase_timestamps):
        raise ValueError(f"Purchase history ({len(purchase_history)}) and timestamps ({len(purchase_timestamps)}) must have same length")
    
    logger.info(f"Processing {len(purchase_history)} items for sequence length {sequence_length}")
    
    # Take only the last 'sequence_length' items
    if len(purchase_history) > sequence_length:
        history = purchase_history[-sequence_length:]
        timestamps = purchase_timestamps[-sequence_length:]
    else:
        # Pad with zeros
        pad_length = sequence_length - len(purchase_history)
        history = [0] * pad_length + purchase_history
        # For timestamps, use None for padding positions
        timestamps = [None] * pad_length + purchase_timestamps
    
    logger.info(f"After padding: {len(history)} items")
    
    # Convert product IDs to indices
    encoded_history = []
    for pid in history:
        if pid == 0:
            encoded_history.append(0)
        else:
            encoded_history.append(product_to_idx.get(pid, 0))
    
    logger.info(f"Encoded history: {encoded_history}")
    
    # Extract temporal features for each position
    time_features_seq = []
    num_features = 13  # Number of features from extract_temporal_features
    
    for i, ts in enumerate(timestamps):
        if ts is None:
            # Padding position - use zeros
            time_features_seq.append([0.0] * num_features)
        else:
            # Calculate time since previous purchase
            if i > 0 and timestamps[i-1] is not None:
                try:
                    hours_diff = (ts - timestamps[i-1]).total_seconds() / 3600
                except Exception as e:
                    logger.error(f"Error calculating time diff: {e}")
                    hours_diff = 0
            else:
                hours_diff = 0
            
            try:
                features = extract_temporal_features(ts, hours_diff, 0)
                time_features_seq.append(features)
            except Exception as e:
                logger.error(f"Error extracting temporal features: {e}")
                time_features_seq.append([0.0] * num_features)
    
    logger.info(f"Generated {len(time_features_seq)} time feature vectors")
    
    # Prepare inputs
    input_product = np.array([encoded_history], dtype=np.int32)
    input_time = np.array([time_features_seq], dtype=np.float32)
    
    logger.info(f"Input shapes - Product: {input_product.shape}, Time: {input_time.shape}")
    
    try:
        # Handle user input
        if len(model.inputs) == 3:  # Has user embedding input
            if user_id and user_to_idx:
                # Encode the user ID
                encoded_user_id = user_to_idx.get(user_id, 0)
            else:
                # Use 0 for unknown user (padding token)
                encoded_user_id = 0
            
            input_user = np.array([[encoded_user_id]], dtype=np.int32)
            logger.info(f"Using user ID: {user_id} -> encoded: {encoded_user_id}")
            predictions = model.predict([input_product, input_time, input_user], verbose=0)[0]
        else:
            predictions = model.predict([input_product, input_time], verbose=0)[0]
        
        logger.info(f"Predictions shape: {predictions.shape}")
        
        # Get top-k indices (excluding padding token 0)
        valid_indices = [i for i in range(len(predictions)) if i != 0 and i in idx_to_product]
        
        if not valid_indices:
            logger.warning("No valid indices found in predictions")
            return []
        
        # Sort by probability
        top_k_indices = sorted(valid_indices, key=lambda i: predictions[i], reverse=True)[:top_k]
        
        # Convert back to product IDs with probabilities
        recommendations = []
        for idx in top_k_indices:
            product_id = idx_to_product[idx]
            probability = float(predictions[idx])
            recommendations.append((product_id, probability))
        
        logger.info(f"Generated {len(recommendations)} recommendations")
        return recommendations
        
    except Exception as e:
        logger.error(f"Error in prediction: {e}", exc_info=True)
        raise

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