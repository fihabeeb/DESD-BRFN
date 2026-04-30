import logging
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile, Form
from pydantic import BaseModel

import predictor
from gradcam import generate_gradcam, overlay_heatmap, colorize_heatmap, to_base64
from recommendation.sigmoid_service import RecommendationService
from recommendation.sigmoid_service_v5_1 import LSTMServiceV5_1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

rec_service = RecommendationService()
rec_service_v5_1 = LSTMServiceV5_1()

MODELS_BASE = os.environ.get("MODELS_BASE", "ml")
VERSIONS_DIR = os.path.join(MODELS_BASE, "versions")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(VERSIONS_DIR, exist_ok=True)
    predictor.load()
    rec_service.load_model()
    rec_service_v5_1.load_model()
    yield


app = FastAPI(title="BRFN ML Service", version="1.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "quality_model_loaded": predictor._model is not None,
        "recommendation_model_loaded": rec_service.is_loaded(),
        "recommendation_max_seq_len": rec_service.max_seq_len,
        "recommendation_v5_1_loaded": rec_service_v5_1.is_loaded(),
    }


# ---------------------------------------------------------------------------
# Quality prediction + Grad-CAM
# ---------------------------------------------------------------------------

@app.post("/predict/quality")
async def predict_quality(image: UploadFile = File(...)):
    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty image file")

    result = predictor.predict(contents)

    img_resized = result.pop("_img_resized")
    img_input = result.pop("_img_input")

    try:
        model = predictor.get_model()
        encoders = predictor.get_encoders()
        cond_classes = list(encoders["condition"].classes_)
        cond_index = cond_classes.index(result["labels"]["condition"])

        heatmap = generate_gradcam(model, img_input, cond_index)
        overlay = overlay_heatmap(heatmap, np.array(img_resized))

        img_arr = np.array(img_resized)
        heatmap_large = cv2.resize(heatmap, (img_arr.shape[1], img_arr.shape[0]), interpolation=cv2.INTER_LINEAR)
        result["gradcam"] = {
            "original": to_base64(img_arr),
            "heatmap": to_base64(colorize_heatmap(heatmap_large)),
            "overlay": to_base64(overlay),
        }
    except Exception as e:
        logger.error("Grad-CAM failed: %s", e)
        result["gradcam"] = None

    return result


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class PurchaseItem(BaseModel):
    product_id: int
    timestamp: str


class RecommendationRequest(BaseModel):
    user_id: int
    purchase_history: List[PurchaseItem]
    top_k: int = 5


@app.post("/predict/recommendations")
def predict_recommendations(request: RecommendationRequest):
    import datetime as dt

    history = []
    for item in request.purchase_history:
        try:
            ts = dt.datetime.fromisoformat(item.timestamp)
        except (ValueError, TypeError):
            ts = [0.0] * 5
        history.append({"product_id": item.product_id, "timestamp": ts})

    recommendations = rec_service.get_recommendations(
        user_id=request.user_id,
        purchase_history=history,
        top_k=request.top_k,
    )

    return {
        "recommendations": recommendations,
        "max_seq_len": rec_service.max_seq_len,
    }


class ExplanationRequest(BaseModel):
    user_id: int
    purchase_history: List[PurchaseItem]
    top_k: int = 5


class SaliencyRequest(BaseModel):
    user_id: int
    target_product_id: int
    purchase_history: List[PurchaseItem]


@app.post("/predict/recommendations/explanation")
def predict_recommendations_explanation(request: ExplanationRequest):
    history = [{"product_id": item.product_id, "timestamp": item.timestamp} for item in request.purchase_history]
    return rec_service_v5_1.get_predictions_with_explanation(
        user_id=request.user_id,
        purchase_history=history,
        top_k=request.top_k,
    )


@app.post("/predict/recommendations/saliency")
def predict_recommendations_saliency(request: SaliencyRequest):
    history = [{"product_id": item.product_id, "timestamp": item.timestamp} for item in request.purchase_history]
    salient = rec_service_v5_1.get_product_saliency(
        user_id=request.user_id,
        target_product_id=request.target_product_id,
        purchase_history=history,
    )
    return {"salient_products": salient}


# ---------------------------------------------------------------------------
# Model upload & hot-reload
# ---------------------------------------------------------------------------

@app.post("/models/upload")
async def upload_model(
    model_type: str = Form(...),
    model_file: UploadFile = File(...),
    mappings_file: Optional[UploadFile] = File(None),
):
    """
    Upload a new model version and activate it immediately.

    model_type: "quality" | "recommendation"
    model_file: .keras file
    mappings_file: .pkl file (required for recommendation, optional for quality)
    """
    if model_type not in ("quality", "recommendation"):
        raise HTTPException(status_code=400, detail="model_type must be 'quality' or 'recommendation'")

    version_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_dir = os.path.join(VERSIONS_DIR, model_type, version_tag)
    os.makedirs(version_dir, exist_ok=True)

    # Save uploaded files to the versioned directory
    model_bytes = await model_file.read()
    versioned_model_path = os.path.join(version_dir, "model.keras")
    with open(versioned_model_path, "wb") as f:
        f.write(model_bytes)

    versioned_mappings_path = None
    if mappings_file:
        mappings_bytes = await mappings_file.read()
        versioned_mappings_path = os.path.join(version_dir, "mappings.pkl")
        with open(versioned_mappings_path, "wb") as f:
            f.write(mappings_bytes)

    # Copy to active paths and reload
    if model_type == "quality":
        active_model = predictor.MODEL_PATH
        active_encoders = predictor.ENCODER_PATH

        shutil.copy2(versioned_model_path, active_model)
        if versioned_mappings_path:
            shutil.copy2(versioned_mappings_path, active_encoders)

        predictor._model = None
        predictor._encoders = None
        predictor.load()
        logger.info("Quality model reloaded from version %s", version_tag)

    else:
        active_model = rec_service.model_path
        active_mappings = rec_service.mappings_path

        shutil.copy2(versioned_model_path, active_model)
        if versioned_mappings_path:
            shutil.copy2(versioned_mappings_path, active_mappings)

        rec_service.load_model()
        logger.info("Recommendation model reloaded from version %s", version_tag)

    return {
        "status": "ok",
        "model_type": model_type,
        "version": version_tag,
        "version_dir": version_dir,
    }


@app.get("/models/versions")
def list_versions():
    """List all uploaded model versions."""
    result = {}
    for model_type in ("quality", "recommendation"):
        type_dir = os.path.join(VERSIONS_DIR, model_type)
        if os.path.isdir(type_dir):
            result[model_type] = sorted(os.listdir(type_dir), reverse=True)
        else:
            result[model_type] = []
    return result
