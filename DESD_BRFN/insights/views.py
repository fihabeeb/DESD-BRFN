import io

import numpy as np
import tensorflow as tf
from PIL import Image
from django.contrib import messages
from django.shortcuts import render

from mainApp.models import CustomerProfile
from ml import predictor
from ml.recommendation.sigmoid_service import LSTMServiceSigmoid
from orders.models import OrderItem
from products.models import Product  # kept in case you use it later
from .gradcam import generate_gradcam, overlay_heatmap, to_base64


def insights_index(request):
    """
    Dashboard-style landing page for the Insights section.
    """
    return render(request, "admin/insights/index.html")


def recommendation_insights(request):
    """
    XAI page for explaining the recommendation process.
    """
    context = {}

    if request.method == "POST":
        customer_id = request.POST.get("customer_id")

        try:
            customer = CustomerProfile.objects.get(id=customer_id)
        except CustomerProfile.DoesNotExist:
            messages.error(request, "Customer not found.")
            return render(request, "admin/insights/recommendation.html", context)

        # Fetch purchase history
        items = (
            OrderItem.objects
            .filter(
                producer_order__payment__user=customer.user,
                producer_order__payment__payment_status="paid",
            )
            .select_related("product")
            .order_by("producer_order__payment__created_at")
        )

        purchase_history = [item.product.id for item in items if item.product]

        service = LSTMServiceSigmoid()
        recommendations = service.get_recommendations(
            customer_id, purchase_history, top_k=5
        )

        context.update(
            {
                "customer": customer,
                "purchase_history": items,
                "recommendations": recommendations,
                "sequence_used": purchase_history[-service.sequence_length :],
            }
        )

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
