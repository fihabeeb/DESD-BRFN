from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from payments.models import PaymentSettlement, SettlementOrder

'''
needs testing!?!?!?!?
'''

# @admin.register(PaymentSettlement)
# class PaymentSettlementAdmin(admin.ModelAdmin):
#     list_display = ['id', 'producer', 'week_start', 'week_end', 
#                     'total_payout', 'payment_status', 'created_at']
#     list_filter = ['payment_status', 'week_start']
#     search_fields = ['producer__business_name']
#     readonly_fields = ['created_at', 'updated_at', 'processed_at']
    
#     actions = ['mark_as_paid', 'generate_reports']
    
#     def mark_as_paid(self, request, queryset):
#         from payments.tasks import process_payment_payout
#         for settlement in queryset:
#             if settlement.payment_status == 'pending':
#                 process_payment_payout.delay(settlement.id)
#         self.message_user(request, f"Processing payments for {queryset.count()} settlements")
#     mark_as_paid.short_description = "Mark selected settlements as paid"
    
#     def generate_reports(self, request, queryset):
#         from payments.tasks import generate_settlement_report
#         for settlement in queryset:
#             generate_settlement_report.delay(settlement.id)
#         self.message_user(request, f"Generating reports for {queryset.count()} settlements")
#     generate_reports.short_description = "Generate reports for selected settlements"


# @admin.register(SettlementOrder)
# class SettlementOrderAdmin(admin.ModelAdmin):
#     list_display = ['settlement', 'order_id', 'order_subtotal', 'order_payout', 'created_at']
#     list_filter = ['created_at']