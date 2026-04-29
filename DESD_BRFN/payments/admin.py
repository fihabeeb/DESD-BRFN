from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from payments.models import PaymentSettlement, SettlementOrder
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.urls import path
from django.shortcuts import redirect
from django.http import HttpResponse, JsonResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.db.models import Sum
from django.core.exceptions import ValidationError

from decimal import Decimal
import csv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from .models import PaymentSettlement, SettlementOrder
from orders.models import OrderProducer
from mainApp.models import ProducerProfile
from .tasks import complete_old_settlements

'''
should be integrity safe 29/4
'''

class DateRangeFilter(SimpleListFilter):
    title = 'date range'
    parameter_name = 'date_range'
    
    def lookups(self, request, model_admin):
        return (
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('quarter', 'This Quarter'),
            ('year', 'This Year'),
            ('custom', 'Custom Range'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'today':
            return queryset.filter(week_start=timezone.now().date())
        elif self.value() == 'week':
            today = timezone.now().date()
            start_of_week = today - timezone.timedelta(days=today.weekday())
            return queryset.filter(week_start=start_of_week)
        elif self.value() == 'month':
            return queryset.filter(
                week_start__year=timezone.now().year,
                week_start__month=timezone.now().month
            )
        elif self.value() == 'quarter':
            current_quarter = (timezone.now().month - 1) // 3 + 1
            return queryset.filter(week_start__quarter=current_quarter)
        elif self.value() == 'year':
            return queryset.filter(week_start__year=timezone.now().year)
        return queryset


class PaymentSettlementAdmin(admin.ModelAdmin):
    """Main admin class for Payment Settlements with financial reporting"""
    change_list_template = 'admin/financial_report.html'
    
    list_display = ['id', 'producer', 'week_start', 'week_end', 'total_orders', 
               'total_commission', 'total_payout', 'settlement_status', 'view_orders_button']
    list_filter = ['settlement_status', 'week_start', 'producer', DateRangeFilter]
    search_fields = ['producer__business_name', 'payment_reference']
    readonly_fields = ['total_orders', 'total_subtotal', 'total_commission', 'total_payout']
    
    actions = ['complete_14_day_settlements']

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        return super().save_model(request, obj, form, change)
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        # Remove the default 'delete_selected' action
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
    
    def delete_model(self, request, obj):
        if obj.orders.exists():
            from django.contrib import messages
            messages.error(
                request,
                f'Cannot delete settlement #{obj.id}: It has {obj.orders.count()} associated orders. '
                'Settlement orders use PROTECT constraint.'
            )
            return
        obj.delete()

    def delete_queryset(self, request, queryset):
        """Bulk delete with protection checks"""
        deletable = []
        protected = 0
        
        for settlement in queryset:
            if settlement.orders.exists():
                protected += 1
            else:
                deletable.append(settlement.id)
        
        if deletable:
            PaymentSettlement.objects.filter(id__in=deletable).delete()
            self.message_user(request, f'Deleted {len(deletable)} settlements.')
        
        if protected:
            self.message_user(
                request, 
                f'Skipped {protected} settlements with existing orders.', 
                level='WARNING'
            )

    def view_orders_button(self, obj):
        """Display a button to view orders for this settlement"""
        return format_html(
            '<a href="{}" class="btn btn-info" style="font-size: 12px; padding: 4px 8px;">View Orders</a>',
            reverse('admin:settlement-orders-view', args=[obj.id])
        )
    view_orders_button.short_description = 'View Orders'
    view_orders_button.allow_tags = True
    
    def view_financial_report(self, request, queryset):
        """Admin action to view financial report for selected settlements"""
        if queryset is None:
            # Called from custom template without queryset
            return redirect('admin:financial-report')
        # Pass selected settlement IDs to the financial report
        selected_ids = ','.join(str(settlement.id) for settlement in queryset)
        return redirect(f'financial-report/?settlement_ids={selected_ids}')
    view_financial_report.short_description = "View Financial Report for Selected Settlements"

    def complete_14_day_settlements(self, request, queryset):
        """
        Admin action to complete settlements that ended 14+ days ago.
        For demo purposes - manually triggers completion check.
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info("COMPLETE_14_DAY action called")
        
        completed_count = complete_old_settlements()
        logger.info(f"COMPLETE_14_DAY: completed_count = {completed_count}")

        if completed_count > 0:
            self.message_user(
                request,
                f'Successfully completed {completed_count} settlement(s) that ended 14+ days ago.'
            )
        else:
            self.message_user(
                request,
                'No settlements found that qualify for completion (period must have ended 14+ days ago).',
                level='INFO'
            )

    complete_14_day_settlements.short_description = "Complete settlements from 14+ days ago"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_site.admin_view(self.financial_report_view), name='financial-report'),
            path('export-csv/', self.admin_site.admin_view(self.export_csv), name='export-csv'),
            path('export-pdf/', self.admin_site.admin_view(self.export_pdf), name='export-pdf'),
            path('order-audit/<int:order_producer_id>/', self.admin_site.admin_view(self.order_audit_view), name='order-audit'),

            path('settlement-orders/<int:settlement_id>/', self.admin_site.admin_view(self.settlement_orders_view), name='settlement-orders-view'),
        ]
        return custom_urls + urls
    
    def settlement_orders_view(self, request, settlement_id):
        """View all orders associated with a specific settlement"""
        try:
            settlement = PaymentSettlement.objects.get(id=settlement_id)
            
            # Get all settlement orders for this settlement
            settlement_orders = SettlementOrder.objects.filter(
                settlement=settlement
            ).select_related(
                'order_producer__payment__user',
                'order_producer__producer'
            )
            
            # Prepare order data for display
            orders_data = []
            total_subtotal = Decimal('0.00')
            total_commission = Decimal('0.00')
            total_payout = Decimal('0.00')
            
            for settlement_order in settlement_orders:
                # Get customer name
                customer_name = 'N/A'
                if settlement_order.order_producer and settlement_order.order_producer.payment:
                    if settlement_order.order_producer.payment.user:
                        customer_name = settlement_order.order_producer.payment.user.get_full_name() or settlement_order.order_producer.payment.user.username
                
                # Verify commission calculation
                expected_commission = (settlement_order.order_subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
                commission_matches = expected_commission == settlement_order.order_commission
                
                orders_data.append({
                    'order_producer_id': settlement_order.order_producer.id,
                    'order_id': settlement_order.order_id,
                    'product_names': settlement_order.get_product_names,
                    'customer_name': customer_name,
                    'completed_date': settlement_order.order_completed_at,
                    'subtotal': settlement_order.order_subtotal,
                    'commission': settlement_order.order_commission,
                    'payout': settlement_order.order_payout,
                    'expected_commission': expected_commission,
                    'commission_matches': commission_matches,
                    'status': settlement_order.order_producer.order_status if settlement_order.order_producer else 'Unknown',
                })
                
                total_subtotal += settlement_order.order_subtotal
                total_commission += settlement_order.order_commission
                total_payout += settlement_order.order_payout
            
            # Calculate verification summary
            verification_summary = {
                'total_orders': len(orders_data),
                'subtotal_matches': total_subtotal == settlement.total_subtotal,
                'commission_matches': total_commission == settlement.total_commission,
                'payout_matches': total_payout == settlement.total_payout,
                'subtotal_difference': total_subtotal - settlement.total_subtotal,
                'commission_difference': total_commission - settlement.total_commission,
                'payout_difference': total_payout - settlement.total_payout,
            }
            
            context = {
                'title': f'Orders for Settlement #{settlement.id}',
                'settlement': settlement,
                'orders': orders_data,
                'summary': {
                    'total_orders': len(orders_data),
                    'total_subtotal': total_subtotal,
                    'total_commission': total_commission,
                    'total_payout': total_payout,
                },
                'verification_summary': verification_summary,
                'opts': self.model._meta,
                'current_filters': request.GET.urlencode(),
            }
            
            return TemplateResponse(request, 'admin/settlement_orders.html', context)
            
        except PaymentSettlement.DoesNotExist:
            self.message_user(request, f'Settlement #{settlement_id} not found.', level='ERROR')
            return redirect('admin:payments_paymentsettlement_changelist')
    
    def financial_report_view(self, request):
        """Main financial report view"""
        # Handle admin actions (POST)
        if request.method == 'POST':
            action = request.POST.get('action')
            if action:
                actions = self.get_actions(request)
                if action in actions:
                    action_func = actions[action][0]
                    response = action_func(self, request, None)
                    if response:
                        return response
                    # Redirect back to the financial report after action
                    return redirect('admin:financial-report')
            # No action selected or action not found - redirect back
            return redirect('admin:financial-report')
        
        # Handle export formats
        format_type = request.GET.get('format')
        if format_type == 'csv':
            return self.export_csv(request)
        elif format_type == 'pdf':
            return self.export_pdf(request)
        
        # Get filter parameters
        date_range = request.GET.get('date_range')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        producer_id = request.GET.get('producer')
        settlement_ids = request.GET.get('settlement_ids')
        
        # Base queryset
        settlements = PaymentSettlement.objects.all()


        # date range
        if date_range and date_range != 'custom':
            today = timezone.now().date()
        if date_range == 'week':
            start_of_week = today - timezone.timedelta(days=today.weekday())
            settlements = settlements.filter(week_start=start_of_week)
        elif date_range == 'month':
            settlements = settlements.filter(
                week_start__year=today.year,
                week_start__month=today.month
            )
        elif date_range == 'quarter':
            current_quarter = (today.month - 1) // 3 + 1
            quarter_months = {
                1: [1, 2, 3],
                2: [4, 5, 6],
                3: [7, 8, 9],
                4: [10, 11, 12]
            }
            settlements = settlements.filter(
                week_start__year=today.year,
                week_start__month__in=quarter_months[current_quarter]
            )
        elif date_range == 'year':
            settlements = settlements.filter(week_start__year=today.year)

        
        # If specific settlements were selected from the action
        if settlement_ids:
            ids = [int(x) for x in settlement_ids.split(',') if x]
            settlements = settlements.filter(id__in=ids)
        
        # Apply filters
        if date_from:
            settlements = settlements.filter(week_start__gte=date_from)
        if date_to:
            settlements = settlements.filter(week_end__lte=date_to)
        if producer_id:
            settlements = settlements.filter(producer_id=producer_id)
        
        # Calculate summary statistics
        summary = settlements.aggregate(
            total_orders=Sum('total_orders'),
            total_subtotal=Sum('total_subtotal'),
            total_commission=Sum('total_commission'),
            total_payout=Sum('total_payout'),
        )
        
        # Get running totals
        running_totals = self.calculate_running_totals(settlements)
        
        # Calculate period summaries
        period_summaries = self.calculate_period_summaries(settlements)
        
        # Verify commission calculations
        verification = self.verify_commission_calculations(settlements)

        # Add admin actions context for custom template
        actions = self.get_actions(request)

        context = {
            'title': 'Financial Report',
            'settlements': settlements,
            'summary': summary,
            'running_totals': running_totals,
            'period_summaries': period_summaries,
            'verification': verification,
            'producers': ProducerProfile.objects.all(),
            'date_from': date_from,
            'date_to': date_to,
            'selected_producer': producer_id,
            'opts': self.model._meta,
            'current_filters': request.GET.urlencode(),
            'selected_date_range': request.GET.get('date_range', ''),
        }

        # Add actions to context if they exist
        if actions:
            # Build choices manually: actions is dict with {'name': (func, name, description), ...}
            action_choices = []
            for name, action_tuple in actions.items():
                func, action_name, description = action_tuple
                action_choices.append((action_name, description))
            
            context['has_actions'] = True
            context['action_choices'] = action_choices
        else:
            context['has_actions'] = False

        return TemplateResponse(request, self.change_list_template, context)
    
    def calculate_running_totals(self, settlements):
        """Calculate running totals across settlements"""
        running_total = Decimal('0.00')
        running_totals = []
        
        for settlement in settlements.order_by('week_start'):
            running_total += settlement.total_payout
            running_totals.append({
                'period': f"{settlement.week_start} - {settlement.week_end}",
                'producer': settlement.producer.business_name,
                'payout': settlement.total_payout,
                'running_total': running_total
            })
        
        return running_totals
    
    def calculate_period_summaries(self, settlements):
        """Calculate summaries by period (weekly/monthly)"""
        summaries = {
            'weekly': {},
            'monthly': {}
        }
        
        for settlement in settlements:
            # Weekly summary
            week_key = f"{settlement.week_start.year}-W{settlement.week_start.isocalendar()[1]}"
            if week_key not in summaries['weekly']:
                summaries['weekly'][week_key] = {
                    'total_orders': 0,
                    'total_commission': Decimal('0.00'),
                    'total_payout': Decimal('0.00')
                }
            summaries['weekly'][week_key]['total_orders'] += settlement.total_orders
            summaries['weekly'][week_key]['total_commission'] += settlement.total_commission
            summaries['weekly'][week_key]['total_payout'] += settlement.total_payout
            
            # Monthly summary
            month_key = settlement.week_start.strftime('%Y-%m')
            if month_key not in summaries['monthly']:
                summaries['monthly'][month_key] = {
                    'total_orders': 0,
                    'total_commission': Decimal('0.00'),
                    'total_payout': Decimal('0.00')
                }
            summaries['monthly'][month_key]['total_orders'] += settlement.total_orders
            summaries['monthly'][month_key]['total_commission'] += settlement.total_commission
            summaries['monthly'][month_key]['total_payout'] += settlement.total_payout
        
        return summaries
    
    def verify_commission_calculations(self, settlements):
        """Verify that commission calculations are accurate"""
        verification_results = []
        
        for settlement in settlements:
            try:
                # Get settlement orders
                settlement_orders = settlement.orders.select_related('order_producer').all()
                manual_commission_total = Decimal('0.00')
                manual_payout_total = Decimal('0.00')
                
                for settlement_order in settlement_orders:
                    # Verify 5% commission with 2 decimal place accuracy
                    expected_commission = (settlement_order.order_subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
                    actual_commission = settlement_order.order_commission
                    
                    if expected_commission != actual_commission:
                        verification_results.append({
                            'settlement_id': settlement.id,
                            'order_producer_id': settlement_order.order_producer.id,
                            'order_id': settlement_order.order_id,
                            'expected_commission': float(expected_commission),
                            'actual_commission': float(actual_commission),
                            'difference': float(expected_commission - actual_commission),
                            'status': 'MISMATCH'
                        })
                    
                    manual_commission_total += actual_commission
                    manual_payout_total += settlement_order.order_payout
                
                # Verify settlement totals (allow for small rounding differences)
                commission_diff = abs(manual_commission_total - settlement.total_commission)
                if commission_diff > Decimal('0.01'):  # More than 1 cent difference
                    verification_results.append({
                        'settlement_id': settlement.id,
                        'type': 'SETTLEMENT_TOTAL_MISMATCH',
                        'expected_commission': float(manual_commission_total),
                        'actual_commission': float(settlement.total_commission),
                        'difference': float(manual_commission_total - settlement.total_commission)
                    })
                    
            except Exception as e:
                verification_results.append({
                    'settlement_id': settlement.id,
                    'type': 'ERROR',
                    'error_message': str(e)
                })
        
        return verification_results
    
    def export_csv(self, request):
        """Export financial report to CSV"""
        settlements = self.get_filtered_settlements(request)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="financial_report.csv"'
        
        writer = csv.writer(response)
        
        # Summary section
        writer.writerow(['FINANCIAL REPORT SUMMARY'])
        writer.writerow(['Generated:', timezone.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])
        
        # Column headers
        writer.writerow([
            'Settlement ID', 'Producer', 'Week Start', 'Week End',
            'Total Orders', 'Subtotal', 'Commission (5%)', 'Producer Payout (95%)',
            'Status', 'Paid At'
        ])
        
        # Data rows
        for settlement in settlements:
            writer.writerow([
                settlement.id,
                settlement.producer.business_name,
                settlement.week_start,
                settlement.week_end,
                settlement.total_orders,
                f"{settlement.total_subtotal:.2f}",
                f"{settlement.total_commission:.2f}",
                f"{settlement.total_payout:.2f}",
                settlement.settlement_status,
                settlement.paid_at.strftime('%Y-%m-%d') if settlement.paid_at else ''
            ])
        
        # Totals row
        totals = settlements.aggregate(
            total_orders=Sum('total_orders'),
            total_commission=Sum('total_commission'),
            total_payout=Sum('total_payout')
        )
        
        writer.writerow([])
        writer.writerow(['TOTALS', '', '', '', 
                        totals['total_orders'] if totals['total_orders'] else 0,
                        '', 
                        f"{totals['total_commission']:.2f}" if totals['total_commission'] else "0.00", 
                        f"{totals['total_payout']:.2f}" if totals['total_payout'] else "0.00"])
        
        # Add order details section
        writer.writerow([])
        writer.writerow(['ORDER DETAILS'])
        writer.writerow([
            'Order ID', 'Settlement ID', 'Producer', 'Customer', 
            'Completed Date', 'Subtotal', 'Commission (5%)', 'Payout (95%)'
        ])
        
        for settlement in settlements:
            for settlement_order in settlement.orders.select_related('order_producer').all():
                # Get customer name from the order payment
                customer_name = ''
                if settlement_order.order_producer and settlement_order.order_producer.payment:
                    if settlement_order.order_producer.payment.user:
                        customer_name = settlement_order.order_producer.payment.user.get_full_name() or settlement_order.order_producer.payment.user.username
                
                writer.writerow([
                    settlement_order.order_id,
                    settlement.id,
                    settlement.producer.business_name,
                    customer_name,
                    settlement_order.order_completed_at.strftime('%Y-%m-%d') if settlement_order.order_completed_at else '',
                    f"{settlement_order.order_subtotal:.2f}",
                    f"{settlement_order.order_commission:.2f}",
                    f"{settlement_order.order_payout:.2f}"
                ])
        
        return response
    
    def export_pdf(self, request):
        """Export financial report to PDF"""
        settlements = self.get_filtered_settlements(request)
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="financial_report.pdf"'
        
        doc = SimpleDocTemplate(response, pagesize=landscape(letter))
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#366092'),
            spaceAfter=30
        )
        elements.append(Paragraph("Financial Report", title_style))
        elements.append(Paragraph(f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        elements.append(Spacer(1, 20))
        
        # Summary table
        summary_data = [['Settlement ID', 'Producer', 'Period', 'Orders', 'Commission', 'Payout']]
        
        for settlement in settlements[:20]:  # Limit to 20 for PDF readability
            summary_data.append([
                str(settlement.id),
                settlement.producer.business_name[:30],
                f"{settlement.week_start} - {settlement.week_end}",
                str(settlement.total_orders),
                f"£{settlement.total_commission:.2f}",
                f"£{settlement.total_payout:.2f}"
            ])
        
        # Add totals row
        totals = settlements.aggregate(
            total_orders=Sum('total_orders'),
            total_commission=Sum('total_commission'),
            total_payout=Sum('total_payout')
        )
        
        summary_data.append([
            'TOTALS', '', '', 
            str(totals['total_orders']) if totals['total_orders'] else '0',
            f"£{totals['total_commission']:.2f}" if totals['total_commission'] else "£0.00",
            f"£{totals['total_payout']:.2f}" if totals['total_payout'] else "£0.00"
        ])
        
        table = Table(summary_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        elements.append(table)
        doc.build(elements)
        
        return response
    
    def order_audit_view(self, request, order_producer_id):
        """View for auditing individual orders"""
        try:
            # Find the settlement order by order_producer_id
            settlement_order = SettlementOrder.objects.select_related(
                'settlement__producer', 
                'order_producer__payment__user'
            ).get(order_producer_id=order_producer_id)
            
            # Calculate verification
            expected_commission = (settlement_order.order_subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
            
            # Get customer name
            customer_name = ''
            if settlement_order.order_producer and settlement_order.order_producer.payment:
                if settlement_order.order_producer.payment.user:
                    customer_name = settlement_order.order_producer.payment.user.get_full_name() or settlement_order.order_producer.payment.user.username
            
            audit_data = {
                'order_producer_id': settlement_order.order_producer.id,
                'order_id': settlement_order.order_id,
                'settlement_id': settlement_order.settlement.id,
                'producer': settlement_order.settlement.producer.business_name,
                'customer': customer_name,
                'completed_date': settlement_order.order_completed_at.isoformat() if settlement_order.order_completed_at else None,
                'subtotal': float(settlement_order.order_subtotal),
                'commission': float(settlement_order.order_commission),
                'payout': float(settlement_order.order_payout),
                'commission_rate': '5%',
                'verification': {
                    'calculated_commission': float(expected_commission),
                    'matches_record': float(expected_commission) == float(settlement_order.order_commission),
                    'difference': float(expected_commission - settlement_order.order_commission)
                },
                'order_status': settlement_order.order_producer.order_status if settlement_order.order_producer else None,
                'settlement_status': settlement_order.settlement.settlement_status,
                'paid_at': settlement_order.settlement.paid_at.isoformat() if settlement_order.settlement.paid_at else None
            }
            
            return JsonResponse(audit_data)
            
        except SettlementOrder.DoesNotExist:
            # Try to find the OrderProducer directly
            try:
                order_producer = OrderProducer.objects.select_related('payment__user', 'producer').get(id=order_producer_id)
                
                # Check if it's been settled
                settlement_order = SettlementOrder.objects.filter(order_producer=order_producer).first()
                
                if settlement_order:
                    # Found through relationship
                    expected_commission = (order_producer.producer_subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
                    
                    audit_data = {
                        'order_producer_id': order_producer.id,
                        'order_id': order_producer.payment.id if order_producer.payment else None,
                        'producer': order_producer.producer.business_name if order_producer.producer else 'Unknown',
                        'customer': order_producer.payment.user.get_full_name() or order_producer.payment.user.username if order_producer.payment and order_producer.payment.user else 'Unknown',
                        'completed_date': order_producer.completed_at.isoformat() if order_producer.completed_at else None,
                        'subtotal': float(order_producer.producer_subtotal),
                        'commission': float(order_producer.commission),
                        'payout': float(order_producer.producer_payout),
                        'commission_rate': '5%',
                        'verification': {
                            'calculated_commission': float(expected_commission),
                            'matches_record': float(expected_commission) == float(order_producer.commission),
                            'difference': float(expected_commission - order_producer.commission)
                        },
                        'order_status': order_producer.order_status,
                        'is_settled': order_producer.is_settled,
                        'settlement_id': order_producer.settlement_id,
                        'settled_at': order_producer.settled_at.isoformat() if order_producer.settled_at else None,
                        'note': 'This order has been settled but not found in SettlementOrder table'
                    }
                    
                    return JsonResponse(audit_data)
                else:
                    # Not settled yet
                    expected_commission = (order_producer.producer_subtotal * Decimal('0.05')).quantize(Decimal('0.01'))
                    
                    audit_data = {
                        'order_producer_id': order_producer.id,
                        'order_id': order_producer.payment.id if order_producer.payment else None,
                        'producer': order_producer.producer.business_name if order_producer.producer else 'Unknown',
                        'customer': order_producer.payment.user.get_full_name() or order_producer.payment.user.username if order_producer.payment and order_producer.payment.user else 'Unknown',
                        'completed_date': order_producer.completed_at.isoformat() if order_producer.completed_at else None,
                        'subtotal': float(order_producer.producer_subtotal),
                        'commission': float(order_producer.commission),
                        'payout': float(order_producer.producer_payout),
                        'commission_rate': '5%',
                        'verification': {
                            'calculated_commission': float(expected_commission),
                            'matches_record': float(expected_commission) == float(order_producer.commission),
                            'difference': float(expected_commission - order_producer.commission)
                        },
                        'order_status': order_producer.order_status,
                        'is_settled': order_producer.is_settled,
                        'note': 'This order has not been settled yet'
                    }
                    
                    return JsonResponse(audit_data)
                    
            except OrderProducer.DoesNotExist:
                return JsonResponse({'error': f'Order Producer {order_producer_id} not found'}, status=404)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def get_filtered_settlements(self, request):
        """Get filtered settlements based on request parameters"""
        settlements = PaymentSettlement.objects.all()
        
        if request.GET.get('date_from'):
            settlements = settlements.filter(week_start__gte=request.GET['date_from'])
        if request.GET.get('date_to'):
            settlements = settlements.filter(week_end__lte=request.GET['date_to'])
        if request.GET.get('producer'):
            settlements = settlements.filter(producer_id=request.GET['producer'])
        if request.GET.get('settlement_ids'):
            ids = [int(x) for x in request.GET['settlement_ids'].split(',') if x]
            settlements = settlements.filter(id__in=ids)
        
        return settlements


# Register the admin
admin.site.register(PaymentSettlement, PaymentSettlementAdmin)