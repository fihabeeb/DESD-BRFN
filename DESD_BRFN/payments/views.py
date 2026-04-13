from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone
from django.http import HttpResponse
import csv
import io

from django.template.loader import render_to_string

from payments.utils import calculate_tax_year
from payments.models import PaymentSettlement, SettlementOrder
from mainApp.decorators import producer_required



@login_required
@producer_required
def payment_history(request):
    """View payment history with YTD running total"""
    producer = request.user.producer_profile
    
    # Get all settlements
    settlements = PaymentSettlement.objects.filter(
        producer=producer
    ).order_by('-week_start')

    # Get available tax years for filter dropdown
    available_tax_years = PaymentSettlement.get_available_tax_years(producer)

    # filters
    tax_year = request.GET.get('tax_year')
    if tax_year:
        settlements = settlements.filter(tax_year=tax_year)

    # stats card
    stats = {
        'total_orders': settlements.aggregate(total=Sum('total_orders'))['total'] or 0,
        'total_subtotal': settlements.aggregate(total=Sum('total_subtotal'))['total'] or Decimal('0.00'),
        'total_commission': settlements.aggregate(total=Sum('total_commission'))['total'] or Decimal('0.00'),
        'total_payout': settlements.aggregate(total=Sum('total_payout'))['total'] or Decimal('0.00'),
    }
    
    status = request.GET.get('status')
    if status:
        settlements = settlements.filter(settlement_status=status)
    
    # Calculate running total (NUMBER 8)
    running_total = Decimal('0.00')
    for settlement in settlements:
        running_total += settlement.total_payout
        settlement.running_total = running_total  # Add as attribute

    
    
    # Calculate YTD (year-to-date)
    today = timezone.now().date()
    current_tax_year = calculate_tax_year(today)
    
    ytd_total = PaymentSettlement.objects.filter(
        producer=producer,
        tax_year=current_tax_year,
        settlement_status='completed'
    ).aggregate(total=Sum('total_payout'))['total'] or Decimal('0.00')

    # Pagination
    paginator = Paginator(settlements, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'settlements': settlements,
        'stats': stats,
        'ytd_total': ytd_total,
        'current_tax_year': current_tax_year,
        'available_tax_years': available_tax_years,
        'selected_tax_year': tax_year,
        'producer': producer,
    }
    
    return render(request, 'payments/settlement.html', context)


@login_required
@producer_required
def settlement_detail(request, settlement_id):
    """
    View detailed settlement information, 
    showing only weekly stats and not year stats
    """
    producer = request.user.producer_profile
    
    settlement = get_object_or_404(
        PaymentSettlement,
        id=settlement_id,
        producer=producer
    )
    
    # Get YTD total for NUMBER 8
    today = timezone.now().date()
    current_tax_year = calculate_tax_year(today)

    ytd_total = PaymentSettlement.objects.filter(
        producer= producer,
        tax_year = current_tax_year,
        settlement_status = 'completed'
    ).aggregate(total=Sum('total_payout'))['total'] or Decimal('0.00')
    
    # Get orders in this settlement
    orders = settlement.orders.select_related(
        'order_producer__payment__user'
    )
    
    context = {
        'settlement': settlement,
        'orders': orders,
        'ytd_total': ytd_total,
        'tax_year_display': settlement.tax_year_display,
        'tax_year_start': settlement.tax_year_start,
        'tax_year_end': settlement.tax_year_end,
        'producer': producer,
    }
    
    return render(request, 'payments/settlement_detail.html', context)

# =========
# downloads
# =========

@login_required
@producer_required
def download_all_settlements_csv(request):
    '''
    Download all settlements for a producer as CSV (for tax year summary)
    '''
    producer = request.user.producer_profile
    
    # Get filters from request
    tax_year = request.GET.get('tax_year')
    status = request.GET.get('status')
    
    # Base queryset
    settlements = PaymentSettlement.objects.filter(producer=producer).order_by('-week_start')
    
    # Apply filters
    if tax_year:
        settlements = settlements.filter(tax_year=tax_year)
    if status:
        settlements = settlements.filter(settlement_status=status)
    
    if not settlements.exists():
        # Return empty CSV if no settlements
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="no_settlements.csv"'
        writer = csv.writer(response)
        writer.writerow(['No settlements found for the selected criteria.'])
        return response
    
    # Create CSV response
    filename = f"all_settlements_{producer.business_name}_{timezone.now().strftime('%Y%m%d')}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Header
    writer.writerow(['BRISTOL REGIONAL FOOD NETWORK - ALL PAYMENT SETTLEMENTS'])
    writer.writerow(['Producer', producer.business_name])
    writer.writerow(['Generated', timezone.now().strftime('%Y-%m-%d %H:%M:%S')])
    if tax_year:
        writer.writerow(['Tax Year Filter', tax_year])
    if status:
        writer.writerow(['Status Filter', status])
    writer.writerow([])
    
    # Summary of all settlements
    total_orders = sum(s.total_orders for s in settlements)
    total_subtotal = sum(s.total_subtotal for s in settlements)
    total_commission = sum(s.total_commission for s in settlements)
    total_payout = sum(s.total_payout for s in settlements)
    
    writer.writerow(['TOTAL SUMMARY'])
    writer.writerow(['Total Orders', total_orders])
    writer.writerow(['Total Subtotal', f"£{total_subtotal:.2f}"])
    writer.writerow(['Total Commission', f"£{total_commission:.2f}"])
    writer.writerow(['Total Payout', f"£{total_payout:.2f}"])
    writer.writerow([])
    
    # Individual settlement details
    writer.writerow(['INDIVIDUAL SETTLEMENTS'])
    writer.writerow([
        'Settlement ID',
        'Week Start',
        'Week End',
        'Tax Year',
        'Orders',
        'Subtotal',
        'Commission',
        'Payout',
        'Status',
        'Paid Date'
    ])
    
    for settlement in settlements:
        writer.writerow([
            settlement.id,
            settlement.week_start,
            settlement.week_end,
            settlement.tax_year,
            settlement.total_orders,
            f"£{settlement.total_subtotal:.2f}",
            f"£{settlement.total_commission:.2f}",
            f"£{settlement.total_payout:.2f}",
            settlement.settlement_status,
            settlement.paid_at.strftime('%Y-%m-%d') if settlement.paid_at else ''
        ])
    
    # For each settlement, list its orders
    writer.writerow([])
    writer.writerow(['DETAILED ORDER BREAKDOWN'])
    
    for settlement in settlements:
        writer.writerow([])
        writer.writerow([f'Settlement #{settlement.id} - Week of {settlement.week_start}'])
        writer.writerow([
            'Order ID',
            'Order Date',
            'Customer Name',
            'Customer Postcode',
            'Subtotal',
            'Commission',
            'Payout'
        ])
        
        orders = settlement.orders.all()
        for order in orders:
            writer.writerow([
                order.order_id,
                order.order_created_at.strftime('%Y-%m-%d') if order.order_created_at else '',
                order.customer_name,
                order.customer_postcode,
                f"£{order.order_subtotal:.2f}",
                f"£{order.order_commission:.2f}",
                f"£{order.order_payout:.2f}"
            ])
    
    writer.writerow([])
    writer.writerow(['END OF REPORT'])
    
    return response


@login_required
@producer_required
def download_settlement_csv(request, settlement_id):
    '''
    Download a single settlement as CSV file for tax records
    '''
    # Get settlement and verify ownership
    settlement = get_object_or_404(
        PaymentSettlement,
        id=settlement_id,
        producer=request.user.producer_profile
    )
    
    # Get all orders in this settlement
    orders = settlement.orders.select_related(
        'order_producer__payment__user'
    ).all()
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="settlement_{settlement.id}_{settlement.week_start}.csv"'
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Write header information
    writer.writerow(['BRISTOL REGIONAL FOOD NETWORK - PAYMENT SETTLEMENT'])
    writer.writerow([])
    writer.writerow(['Settlement ID', settlement.id])
    writer.writerow(['Producer', settlement.producer.business_name])
    writer.writerow(['Tax Year', settlement.tax_year])
    writer.writerow(['Period', f"{settlement.week_start} to {settlement.week_end}"])
    writer.writerow(['Generated', timezone.now().strftime('%Y-%m-%d %H:%M:%S')])
    writer.writerow([])
    
    # Write summary
    writer.writerow(['SUMMARY'])
    writer.writerow(['Total Orders', settlement.total_orders])
    writer.writerow(['Total Subtotal', f"£{settlement.total_subtotal:.2f}"])
    writer.writerow(['Total Commission (5%)', f"£{settlement.total_commission:.2f}"])
    writer.writerow(['Total Payout', f"£{settlement.total_payout:.2f}"])
    writer.writerow([])
    
    # Write order details header
    writer.writerow(['ORDER DETAILS'])
    writer.writerow([
        'Order ID',
        'Order Date',
        'Completed Date',
        'Customer Name',
        'Customer Postcode',
        'Subtotal (£)',
        'Commission (£)',
        'Payout (£)'
    ])
    
    # Write order rows
    for order in orders:
        writer.writerow([
            order.order_id,
            order.order_created_at.strftime('%Y-%m-%d %H:%M') if order.order_created_at else '',
            order.order_completed_at.strftime('%Y-%m-%d %H:%M') if order.order_completed_at else '',
            order.customer_name,
            order.customer_postcode,
            f"{order.order_subtotal:.2f}",
            f"{order.order_commission:.2f}",
            f"{order.order_payout:.2f}"
        ])
    
    # Write footer
    writer.writerow([])
    writer.writerow(['END OF REPORT'])
    writer.writerow(['This is an official record of payment settlement.'])
    writer.writerow(['For any queries, please contact finance@bristolfoodnetwork.com'])
    
    return response
    pass


@login_required
@producer_required
def download_settlement_pdf(request, settlement_id):
    '''
    Download a single settlement as PDF for tax records
    '''
    try:
        from payments.pdf_gen import generate_settlement_pdf
        # Get settlement and verify ownership
        settlement = get_object_or_404(
            PaymentSettlement,
            id=settlement_id,
            producer=request.user.producer_profile
        )
        
        # Get all orders in this settlement
        orders = settlement.orders.select_related(
            'order_producer__payment__user'
        ).all()
        
        # Generate PDF - this returns a BytesIO object
        pdf_buffer = generate_settlement_pdf(settlement, orders)
        
        # IMPORTANT: Get the bytes from the buffer
        pdf_bytes = pdf_buffer.getvalue()
        
        # Create HTTP response with the PDF bytes
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="settlement_{settlement.id}_{settlement.week_start}.pdf"'
        
        return response
        
    except PaymentSettlement.DoesNotExist:
        return HttpResponse("Settlement not found.", status=404)
        
    except Exception as e:
        return HttpResponse(f"Error generating PDF: {str(e)}", status=500)

# @login_required
# @producer_required
# def download_settlement_pdf(request, settlement_id):
#     '''
    
#     '''
#     pass