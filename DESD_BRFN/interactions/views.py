import csv
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.utils import timezone
from .models import UserInteraction


@staff_member_required
def export_csv(request):
    """
    Download all user interactions as CSV for offline model retraining.
    Supports optional query params: ?type=purchased&from=2025-01-01&to=2025-12-31
    """
    qs = UserInteraction.objects.select_related('user', 'product').order_by('timestamp')

    interaction_type = request.GET.get('type')
    if interaction_type:
        qs = qs.filter(interaction_type=interaction_type)

    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    if date_from:
        qs = qs.filter(timestamp__date__gte=date_from)
    if date_to:
        qs = qs.filter(timestamp__date__lte=date_to)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="interactions_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        'id', 'user_id', 'username', 'session_key',
        'interaction_type', 'product_id', 'product_name',
        'metadata', 'timestamp',
    ])

    for obj in qs:
        writer.writerow([
            obj.id,
            obj.user_id,
            obj.user.username if obj.user else '',
            obj.session_key,
            obj.interaction_type,
            obj.product_id,
            obj.product.name if obj.product else '',
            obj.metadata,
            obj.timestamp.isoformat(),
        ])

    return response
