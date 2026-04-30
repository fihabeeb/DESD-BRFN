import csv
from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from .models import UserInteraction


def export_interactions_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="interactions_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow(['id', 'user_id', 'username', 'session_key', 'interaction_type',
                     'product_id', 'product_name', 'metadata', 'timestamp'])
    for obj in queryset.select_related('user', 'product'):
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


export_interactions_csv.short_description = 'Export selected interactions as CSV'


@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'interaction_type', 'product', 'session_key')
    list_filter = ('interaction_type', 'timestamp')
    search_fields = ('user__username', 'product__name', 'session_key')
    readonly_fields = ('timestamp', 'metadata')
    date_hierarchy = 'timestamp'
    actions = [export_interactions_csv]
