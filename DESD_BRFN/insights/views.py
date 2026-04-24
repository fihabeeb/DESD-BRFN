import io

import numpy as np
import tensorflow as tf
from PIL import Image
from django.contrib import messages
from django.shortcuts import render

from mainApp.models import CustomerProfile
from ml.recommendation.sigmoid_service_v5_1 import LSTMServiceV5_1
from orders.models import OrderItem
from products.models import Product
from .gradcam import generate_gradcam, overlay_heatmap, to_base64


def insights_index(request):
    """
    Dashboard-style landing page for the Insights section.
    """
    return render(request, "admin/insights/index.html")

def recommendation_insights(request):
    """
    XAI page for V5.1 recommendation transparency.
    Shows recommendations + attention weights + product saliency.
    """
    context = {}

    if request.method == "POST":
        customer_id = request.POST.get("customer_id")

        try:
            customer = CustomerProfile.objects.get(id=customer_id)
        except CustomerProfile.DoesNotExist:
            messages.error(request, "Customer not found.")
            return render(request, "admin/insights/recommendation.html", context)

        service = LSTMServiceV5_1()
        service.load_model()

        TOP_K = 10
        result = service.get_predictions_with_explanation(
            user_id=customer.user.id,
            top_k=TOP_K
        )

        salient_products = []
        if result.get('recommendations'):
            top_rec = result['recommendations'][0]
            if hasattr(top_rec.get('product'), 'id'):
                salient_products = service.get_product_saliency(
                    customer.user.id,
                    top_rec['product'].id
                )

        recommendations = result.get('recommendations', [])
        # Add display_score (percentage) for the score bars
        for rec in recommendations:
            rec['display_score'] = rec['score'] * 100

        context.update({
            "customer": customer,
            "TOP_K_used": TOP_K,
            "recommendations": recommendations,
            "attention_weights": result.get('attention_weights', []),
            "order_details": result.get('order_details', []),
            "num_orders": result.get('num_orders', 0),
            "salient_products": salient_products,
        })

    return render(request, "admin/insights/recommendation.html", context)


def classification_insights(request):
    """
    Image classification insights with simple Grad-CAM explanation (condition head only).
    """
    context = {}

    if request.method == "POST" and request.FILES.get("image"):
        image_file = request.FILES["image"]

        # Run existing predictor (quality + labels)
        result = predictor.predict(image_file)
        context["result"] = result

        # Rewind file pointer and reload image for Grad-CAM
        image_file.seek(0)
        img = Image.open(io.BytesIO(image_file.read())).convert("RGB")
        img_resized = img.resize((128, 128))
        img_norm = np.array(img_resized) / 255.0
        img_input = np.expand_dims(img_norm, axis=0)

        # Load model ONLY inside Insights
        model = tf.keras.models.load_model("ml/best_model.keras")

        # Condition head index based on predicted label ("Healthy" or "Rotten")
        condition_label = result["labels"]["condition"]
        cond_classes = list(predictor._encoders["condition"].classes_)
        cond_index = cond_classes.index(condition_label)

        # Generate Grad-CAM for the predicted condition class
        heatmap = generate_gradcam(model, img_input, cond_index)

        # Overlay on the original resized image
        overlay = overlay_heatmap(heatmap, np.array(img_resized))

        # Convert to base64 for template
        context["original"] = to_base64(np.array(img_resized))
        context["heatmap"] = to_base64((heatmap * 255).astype("uint8"))
        context["overlay"] = to_base64(overlay)

    return render(request, "admin/insights/classification.html", context)
