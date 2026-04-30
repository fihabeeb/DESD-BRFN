import os
import requests as http_client

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from mainApp.models import CustomerProfile
from ml import predictor
from ml.recommendation.sigmoid_service import LSTMServiceSigmoid
from orders.models import OrderItem

ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml-service:8001")


def insights_index(request):
    return render(request, "admin/insights/index.html")


def recommendation_insights(request):
    context = {}

    if request.method == "POST":
        customer_id = request.POST.get("customer_id")

        try:
            customer = CustomerProfile.objects.get(id=customer_id)
        except CustomerProfile.DoesNotExist:
            messages.error(request, "Customer not found.")
            return render(request, "admin/insights/recommendation.html", context)

        items = (
            OrderItem.objects
            .filter(
                producer_order__payment__user=customer.user,
                producer_order__payment__payment_status="paid",
            )
            .select_related("product", "producer_order__payment")
            .order_by("producer_order__payment__created_at")
        )

        purchase_history = [
            (item.product.id, item.producer_order.payment.created_at)
            for item in items
            if item.product
        ]

        service = LSTMServiceSigmoid()
        recommendations = service.get_recommendations(
            customer.user.id, purchase_history, top_k=5
        )

        context.update(
            {
                "customer": customer,
                "purchase_history": items,
                "recommendations": recommendations,
                "sequence_used": [pid for pid, _ in purchase_history[-service.sequence_length:]],
            }
        )

    return render(request, "admin/insights/recommendation.html", context)


def classification_insights(request):
    context = {}

    if request.method == "POST" and request.FILES.get("image"):
        image_file = request.FILES["image"]

        result = predictor.predict(image_file)
        if result is None:
            messages.error(request, "ML service unavailable. Please try again later.")
            return render(request, "admin/insights/classification.html", context)

        context["result"] = result

        gradcam = result.get("gradcam")
        if gradcam:
            context["original"] = gradcam["original"]
            context["heatmap"] = gradcam["heatmap"]
            context["overlay"] = gradcam["overlay"]

    return render(request, "admin/insights/classification.html", context)


@staff_member_required
def upload_model(request):
    """
    Admin page for uploading a new ML model into the ml-service.
    Accepts a .keras model file and an optional .pkl mappings/encoders file.
    """
    context = {}

    if request.method == "POST":
        model_type = request.POST.get("model_type")
        model_file = request.FILES.get("model_file")
        mappings_file = request.FILES.get("mappings_file")

        if not model_type or not model_file:
            messages.error(request, "Model type and model file are required.")
            return render(request, "admin/insights/upload_model.html", context)

        files = {"model_file": (model_file.name, model_file.read(), "application/octet-stream")}
        if mappings_file:
            files["mappings_file"] = (mappings_file.name, mappings_file.read(), "application/octet-stream")

        try:
            response = http_client.post(
                f"{ML_SERVICE_URL}/models/upload",
                data={"model_type": model_type},
                files=files,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            messages.success(
                request,
                f"Model uploaded and activated (version: {data['version']}).",
            )
            context["result"] = data
        except Exception as e:
            messages.error(request, f"Upload failed: {e}")

    # Fetch existing versions for display
    try:
        resp = http_client.get(f"{ML_SERVICE_URL}/models/versions", timeout=5)
        context["versions"] = resp.json()
    except Exception:
        context["versions"] = {}

    return render(request, "admin/insights/upload_model.html", context)
