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

# ============================================
# DATA EXTRACTION & PREPROCESSING
# ============================================

def get_user_sequences():
    """
    Extract user purchase sequences from paid orders.
    
    Returns:
        dict: {user_id: [product_id, product_id, ...]} ordered by time
    """
    sequences = defaultdict(list)
    
    # Filter only paid orders
    order_items = OrderItem.objects.filter(
        producer_order__payment__payment_status='paid'
    ).select_related('product', 'producer_order__payment')
    
    # Sort by payment creation time (chronological order)
    order_items = order_items.order_by('producer_order__payment__created_at')
    
    for item in order_items:
        user = item.producer_order.payment.user
        product = item.product
        
        if not user or not product:
            continue
        
        # Repeat product ID based on quantity purchased
        for _ in range(item.quantity):
            sequences[user.id].append(product.id)
    
    return dict(sequences)


def build_training_data(sequence_length=3, min_user_sequences=2):
    """
    Create sequences and labels for training.
    
    Args:
        sequence_length: Number of previous items to use for prediction
        min_user_sequences: Minimum sequences per user to include (for filtering)
    
    Returns:
        tuple: (X sequences list, y labels list)
    """
    user_sequences = get_user_sequences()
    
    X = []
    y = []
    user_counts = []
    
    for user_id, seq in user_sequences.items():
        if len(seq) <= sequence_length:
            continue
        
        # Track how many sequences per user
        num_sequences = len(seq) - sequence_length
        user_counts.append(num_sequences)
        
        # Create sliding windows
        for i in range(num_sequences):
            X.append(seq[i:i + sequence_length])
            y.append(seq[i + sequence_length])
    
    # Print statistics
    if user_counts:
        print(f"Users with sufficient data: {len(user_counts)}")
        print(f"Average sequences per user: {np.mean(user_counts):.2f}")
        print(f"Median sequences per user: {np.median(user_counts):.2f}")
        print(f"Max sequences from one user: {max(user_counts)}")
        print(f"Min sequences from one user: {min(user_counts)}")
    
    return X, y


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


def analyze_data_distribution(X_enc, y_enc, product_to_idx):
    """Analyze data distribution for insights."""
    print("\n" + "="*50)
    print("DATA DISTRIBUTION ANALYSIS")
    print("="*50)
    
    # Check sequence lengths
    lengths = [len(seq) for seq in X_enc]
    print(f"Sequence lengths - Min: {min(lengths)}, Max: {max(lengths)}, Mean: {np.mean(lengths):.2f}")
    
    # Check target distribution
    unique, counts = np.unique(y_enc, return_counts=True)
    # Exclude padding token (0) from analysis
    unique = unique[unique != 0]
    counts = counts[1:] if len(counts) > 1 else counts
    
    print(f"Unique products in targets: {len(unique)}")
    print(f"Most common product appears {counts.max()} times ({counts.max()/len(y_enc)*100:.1f}%)")
    print(f"Least common product appears {counts.min()} times")
    
    # Check for class imbalance
    sorted_indices = np.argsort(counts)[::-1]
    print("\nTop 5 most frequent products:")
    for i in range(min(5, len(sorted_indices))):
        idx = sorted_indices[i]
        # Find actual product ID from mapping
        product_id = [k for k, v in product_to_idx.items() if v == unique[idx]][0] if len(unique) > idx else "Unknown"
        print(f"  Product {product_id}: {counts[idx]} times ({counts[idx]/len(y_enc)*100:.1f}%)")
    
    # Calculate class balance metric
    from scipy import stats
    cv = counts.std() / counts.mean() if counts.mean() > 0 else 0
    print(f"\nCoefficient of variation: {cv:.2f} (higher = more imbalanced)")


# ============================================
# MODEL ARCHITECTURE
# ============================================

def build_improved_lstm_model(num_products, sequence_length, embedding_dim=64, lstm_units=128):
    """
    Build improved LSTM model for next-product prediction.
    
    Args:
        num_products: Total number of unique products
        sequence_length: Length of input sequences
        embedding_dim: Dimension of embedding layer
        lstm_units: Number of LSTM units
    
    Returns:
        tensorflow.keras.Model: Compiled LSTM model
    """
    model = Sequential([
        # Embedding layer with masking for padding
        Embedding(
            input_dim=num_products + 1,  # +1 for padding token
            output_dim=embedding_dim,
            mask_zero=True  # Mask padding tokens
        ),
        
        # First LSTM layer with return sequences (bidirectional for better context)
        Bidirectional(LSTM(lstm_units, return_sequences=True, dropout=0.2, recurrent_dropout=0.2)),
        BatchNormalization(),
        Dropout(0.3),
        
        # Second LSTM layer
        Bidirectional(LSTM(lstm_units // 2, return_sequences=False, dropout=0.2, recurrent_dropout=0.2)),
        BatchNormalization(),
        Dropout(0.3),
        
        # Dense layers for better representation
        Dense(128, activation='relu'),
        BatchNormalization(),
        Dropout(0.3),
        
        Dense(64, activation='relu'),
        Dropout(0.2),
        
        # Output layer
        Dense(num_products + 1, activation='softmax')  # +1 for padding token
    ])
    
    # Use a lower learning rate and add label smoothing
    model.compile(
        loss='sparse_categorical_crossentropy',
        optimizer=Adam(learning_rate=0.0005),
        metrics=['accuracy']
    )
    
    return model


# ============================================
# TRAINING PIPELINE
# ============================================

def train_model(sequence_length=3, epochs=50, batch_size=64, validation_split=0.2):
    """
    Complete training pipeline with improved architecture and callbacks.
    
    Args:
        sequence_length: Length of input sequences
        epochs: Number of training epochs
        batch_size: Batch size for training
        validation_split: Fraction of data to use for validation
    
    Returns:
        tuple: (trained_model, product_mappings, history)
    """
    print("Step 1: Building training data...")
    X_raw, y_raw = build_training_data(sequence_length)
    
    if not X_raw:
        raise ValueError("No training data available. Check if there are paid orders in the database.")
    
    print(f"Raw data: {len(X_raw)} sequences, {len(set(y_raw))} unique products")
    
    print("Step 2: Encoding products (reserving 0 for padding)...")
    X_enc, y_enc, p2i, i2p = encode_products(X_raw, y_raw)
    
    num_unique_products = len([k for k in p2i.keys() if k != 0])  # Exclude padding
    print(f"Encoded: {num_unique_products} unique products (+1 padding token)")
    
    # Analyze data distribution
    analyze_data_distribution(X_enc, y_enc, p2i)
    
    print("Step 3: Padding sequences...")
    X_padded = pad_sequences(X_enc, maxlen=sequence_length, padding='pre', truncating='pre')
    
    # Convert to numpy arrays
    X_padded = np.array(X_padded, dtype=np.int32)
    y_enc = np.array(y_enc, dtype=np.int32)
    
    print(f"Input shape: {X_padded.shape}")
    print(f"Output shape: {y_enc.shape}")
    
    # Split data for validation with stratification
    # Note: stratify helps with class imbalance but may break temporal patterns slightly
    # For pure temporal patterns, set stratify=None
    X_train, X_val, y_train, y_val = train_test_split(
        X_padded, y_enc, 
        test_size=validation_split, 
        random_state=42,
    )
    
    print(f"Training samples: {len(X_train)}")
    print(f"Validation samples: {len(X_val)}")
    
    print("Step 4: Building improved LSTM model...")
    model = build_improved_lstm_model(num_unique_products, sequence_length)
    model.summary()
    
    # Callbacks for better training
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
            'ml/recommendation/checkpoint/rec_best_model.keras',
            monitor='val_accuracy',
            save_best_only=True,
            verbose=1
        )
    ]
    
    print("Step 5: Training model...")
    history = model.fit(
        X_train,
        y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_data=(X_val, y_val),
        callbacks=callbacks,
        verbose=1
    )
    
    print("Step 6: Saving model and mappings...")
    # Save the final model
    model.save("ml/recommendation/final/recommendation_model.keras")
    
    mappings = {
        "product_to_idx": p2i,
        "idx_to_product": i2p,
        "sequence_length": sequence_length,
        "num_products": num_unique_products
    }
    
    with open("ml/recommendation/product_mappings.pkl", "wb") as f:
        pickle.dump(mappings, f)
    
    print("\n" + "="*50)
    print("TRAINING SUMMARY")
    print("="*50)
    print(f"Final training accuracy: {history.history['accuracy'][-1]:.4f}")
    print(f"Final validation accuracy: {history.history['val_accuracy'][-1]:.4f}")
    print(f"Best validation accuracy: {max(history.history['val_accuracy']):.4f}")
    print(f"Final validation loss: {history.history['val_loss'][-1]:.4f}")
    print(f"Best validation loss: {min(history.history['val_loss']):.4f}")
    print("Training completed successfully!")
    
    return model, mappings, history


# ============================================
# PREDICTION & RECOMMENDATION
# ============================================

def load_trained_model(model_path="ml/recommendation/final/recommendation_model.keras", 
                       mappings_path="ml/recommendation/product_mappings.pkl"):
    """
    Load trained model and mappings for inference.
    
    Args:
        model_path: Path to saved model
        mappings_path: Path to saved mappings
    
    Returns:
        tuple: (model, product_to_idx, idx_to_product, sequence_length)
    """
    from tensorflow.keras.models import load_model
    
    model = load_model(model_path)
    
    with open(mappings_path, "rb") as f:
        mappings = pickle.load(f)
    
    product_to_idx = mappings["product_to_idx"]
    idx_to_product = mappings["idx_to_product"]
    sequence_length = mappings.get("sequence_length", 3)
    
    return model, product_to_idx, idx_to_product, sequence_length


def recommend_next_products(model, product_to_idx, idx_to_product, 
                           purchase_history, top_k=5):
    """
    Recommend next products based on purchase history.
    
    Args:
        model: Trained LSTM model
        product_to_idx: Mapping from product ID to index
        idx_to_product: Mapping from index to product ID
        purchase_history: List of recent product IDs (in chronological order)
        top_k: Number of recommendations to return
    
    Returns:
        list: Top-k recommended product IDs with probabilities
    """
    sequence_length = model.input_shape[1]
    
    # Take only the last 'sequence_length' items
    if len(purchase_history) > sequence_length:
        history = purchase_history[-sequence_length:]
    else:
        # Pad with zeros if history is shorter than sequence_length
        history = [0] * (sequence_length - len(purchase_history)) + purchase_history
    
    # Convert product IDs to indices
    encoded_history = []
    for pid in history:
        if pid in product_to_idx:
            encoded_history.append(product_to_idx[pid])
        else:
            # Unknown product - use padding token
            print(f"Warning: Unknown product ID {pid}. Using padding token.")
            encoded_history.append(0)
    
    # Reshape for model input
    input_sequence = np.array([encoded_history], dtype=np.int32)
    
    # Get predictions
    predictions = model.predict(input_sequence, verbose=0)[0]
    
    # Get top-k indices (excluding padding token 0)
    valid_indices = [i for i in range(len(predictions)) if i != 0 and i in idx_to_product]
    top_k_indices = sorted(valid_indices, key=lambda i: predictions[i], reverse=True)[:top_k]
    
    # Convert back to product IDs with probabilities
    recommendations = []
    for idx in top_k_indices:
        product_id = idx_to_product[idx]
        probability = predictions[idx]
        recommendations.append((product_id, probability))
    
    return recommendations


def evaluate_model_sample(model, X_val, y_val, idx_to_product, num_samples=10):
    """
    Evaluate model predictions on sample data.
    
    Args:
        model: Trained model
        X_val: Validation features
        y_val: Validation labels
        idx_to_product: Mapping from index to product ID
        num_samples: Number of samples to evaluate
    """
    print("\n" + "="*50)
    print("SAMPLE PREDICTIONS")
    print("="*50)
    
    # Get random samples
    indices = np.random.choice(len(X_val), min(num_samples, len(X_val)), replace=False)
    correct_predictions = 0
    
    for idx in indices:
        sequence = X_val[idx:idx+1]
        true_product_idx = y_val[idx]
        
        # Get prediction
        predictions = model.predict(sequence, verbose=0)[0]
        predicted_idx = np.argmax(predictions)
        confidence = predictions[predicted_idx]
        
        # Convert to actual product IDs
        true_product = idx_to_product.get(true_product_idx, "Unknown")
        predicted_product = idx_to_product.get(predicted_idx, "Unknown")
        
        # Get top-3 predictions (excluding padding)
        valid_indices = [i for i in range(len(predictions)) if i != 0 and i in idx_to_product]
        top_3_indices = sorted(valid_indices, key=lambda i: predictions[i], reverse=True)[:3]
        top_3_products = [(idx_to_product.get(i, "Unknown"), predictions[i]) for i in top_3_indices]
        
        is_correct = predicted_idx == true_product_idx
        if is_correct:
            correct_predictions += 1
        
        print(f"\nInput sequence: {sequence[0].tolist()}")
        print(f"True product: {true_product}")
        print(f"Predicted: {predicted_product} (confidence: {confidence:.4f})")
        print(f"Top 3 predictions: {[(p, f'{c:.4f}') for p, c in top_3_products]}")
        print(f"{'✓' if is_correct else '✗'} Prediction {'correct' if is_correct else 'incorrect'}")
    
    print(f"\nSample accuracy: {correct_predictions}/{len(indices)} = {correct_predictions/len(indices)*100:.1f}%")
    