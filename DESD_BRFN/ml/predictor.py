"""
AI quality prediction for produce images.
Loads the Keras model and encoders once at import time.
"""
import io
import os
import pickle

import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH   = os.path.join(BASE_DIR, "best_model.keras")
ENCODER_PATH = os.path.join(BASE_DIR, "encoders.pkl")
IMG_SIZE = (128, 128)

_model    = None
_encoders = None


def _load():
    global _model, _encoders
    if _model is None:
        import tensorflow as tf
        _model = tf.keras.models.load_model(MODEL_PATH)
    if _encoders is None:
        with open(ENCODER_PATH, "rb") as f:
            _encoders = pickle.load(f)


def predict(image_file):
    """
    Run quality prediction on an uploaded image.

    Args:
        image_file: Django InMemoryUploadedFile from request.FILES

    Returns:
        dict with overall_score, grade, breakdown (condition/color/size scores),
        and labels (the predicted class names with confidence percentages).
    """
    _load()

    # Read and preprocess with Pillow — no cv2 needed
    img = Image.open(io.BytesIO(image_file.read())).convert("RGB")
    img_resized = img.resize(IMG_SIZE)
    img_norm    = np.array(img_resized) / 255.0
    img_input   = np.expand_dims(img_norm, axis=0)

    # Run prediction
    cond_pred, col_pred, size_pred = _model.predict(img_input, verbose=0)

    # Decode predicted class labels
    condition = _encoders["condition"].inverse_transform([np.argmax(cond_pred)])[0]
    colour    = _encoders["colour"].inverse_transform([np.argmax(col_pred)])[0]
    size      = _encoders["size"].inverse_transform([np.argmax(size_pred)])[0]

    # Raw confidence values (0–100)
    cond_conf = float(np.max(cond_pred) * 100)
    col_conf  = float(np.max(col_pred)  * 100)
    size_conf = float(np.max(size_pred) * 100)

    # Quality scores:
    #   condition — high confidence in "Healthy" is good; high confidence in
    #               "Unhealthy" is bad, so invert it.
    #   colour / size — confidence is used directly as a quality proxy.
    condition_score = round(cond_conf if condition == "Healthy" else 100 - cond_conf, 1)
    color_score     = round(col_conf, 1)
    size_score      = round(size_conf, 1)

    overall = round((condition_score + color_score + size_score) / 3)

    if overall >= 80:
        grade = "A"
    elif overall >= 70:
        grade = "B"
    elif overall >= 60:
        grade = "C"
    elif overall >= 50:
        grade = "D"
    else:
        grade = "F"

    return {
        "overall_score": overall,
        "grade": grade,
        "breakdown": {
            "condition": condition_score,
            "color":     color_score,
            "size":      size_score,
        },
        "labels": {
            "condition": condition,
            "colour":    colour,
            "size":      size,
        },
        "confidences": {
            "condition": round(cond_conf, 1),
            "colour":    round(col_conf,  1),
            "size":      round(size_conf, 1),
        },
    }
