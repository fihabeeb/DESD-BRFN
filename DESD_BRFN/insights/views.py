import os
import requests as http_client

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from mainApp.models import CustomerProfile

ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://ml-service:8001")
from products.models import Product


def insights_index(request):
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

        from orders.models import OrderItem
        from products.models import Product

        order_items = OrderItem.objects.filter(
            producer_order__payment__user_id=customer.user.id,
            producer_order__payment__payment_status="paid",
        ).select_related("producer_order__payment").order_by(
            "producer_order__payment__created_at",
            "producer_order__id",
        )
        purchase_history = [
            {
                "product_id": item.product_id,
                "timestamp": item.producer_order.payment.created_at.isoformat(),
            }
            for item in order_items
            for _ in range(item.quantity)
        ]

        TOP_K = 10
        try:
            response = http_client.post(
                f"{ML_SERVICE_URL}/predict/recommendations/explanation",
                json={"user_id": customer.user.id, "purchase_history": purchase_history, "top_k": TOP_K},
                timeout=15,
            )
            response.raise_for_status()
            result = response.json()
        except Exception as e:
            messages.error(request, f"ML service unavailable: {e}")
            return render(request, "admin/insights/recommendation.html", context)

        raw_recs = result.get("recommendations", [])
        product_ids = [r["product_id"] for r in raw_recs]
        products_by_id = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
        recommendations = [
            {**r, "product": products_by_id[r["product_id"]], "display_score": r["score"] * 100}
            for r in raw_recs
            if r["product_id"] in products_by_id
        ]

        salient_products = []
        if recommendations:
            top_product_id = recommendations[0]["product_id"]
            try:
                sal_response = http_client.post(
                    f"{ML_SERVICE_URL}/predict/recommendations/saliency",
                    json={
                        "user_id": customer.user.id,
                        "target_product_id": top_product_id,
                        "purchase_history": purchase_history,
                    },
                    timeout=15,
                )
                sal_response.raise_for_status()
                sal_data = sal_response.json().get("salient_products", [])
                sal_product_ids = [s["product_id"] for s in sal_data]
                sal_products_by_id = {p.id: p for p in Product.objects.filter(id__in=sal_product_ids)}
                salient_products = [
                    {**s, "product_name": sal_products_by_id[s["product_id"]].name}
                    for s in sal_data
                    if s["product_id"] in sal_products_by_id
                ]
            except Exception:
                salient_products = []

        context.update({
            "customer": customer,
            "TOP_K_used": TOP_K,
            "recommendations": recommendations,
            "attention_weights": result.get("attention_weights", []),
            "order_details": result.get("order_details", []),
            "num_orders": result.get("num_orders", 0),
            "salient_products": salient_products,
        })

    return render(request, "admin/insights/recommendation.html", context)


def classification_insights(request):
    context = {}

    if request.method == "POST" and request.FILES.get("image"):
        image_file = request.FILES["image"]

        try:
            response = http_client.post(
                f"{ML_SERVICE_URL}/predict/quality",
                files={"image": (image_file.name, image_file.read(), image_file.content_type)},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
        except Exception:
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
