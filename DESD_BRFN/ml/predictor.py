"""Thin HTTP client — delegates quality prediction to the ml-service container."""
import os
import logging
import requests

logger = logging.getLogger(__name__)

ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml-service:8001")


def predict(image_file):
    """
    Run quality prediction on an uploaded image via the ml-service.

    Args:
        image_file: Django InMemoryUploadedFile from request.FILES

    Returns:
        dict with overall_score, grade, breakdown, labels, confidences, gradcam
    """
    try:
        image_file.seek(0)
        response = requests.post(
            f"{ML_SERVICE_URL}/predict/quality",
            files={"image": (image_file.name, image_file.read(), "image/jpeg")},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error("ml-service quality prediction failed: %s", e)
        return None
