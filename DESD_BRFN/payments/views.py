from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone

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


# @login_required
# @producer_required
# def settlement_history(request):
#     '''
    
#     '''
#     producer = request.user.producer_profile

#     settlements = PaymentSettlement.objects.filter(
#         producer=producer
#     ).order_by('-week_start')

#     # filters
#     year = request.GET.get('year')
#     if year:
#         settlements = settlements.filter(week_start__year=year)

#     # Calculate summary
#     total_paid = settlements.filter(payment_status='completed').aggregate(
#         total=Sum('total_payout')
#     )['total'] or Decimal('0.00')

#     # total_pending=settlements.filter(payment_status='pending').aggregate(
#     #     total=Sum('total_payout')
#     # )['total'] or Decimal('0.00')

#     total_orders = settlements.aggregate(
#             total=Sum('total_orders')
#     )['total'] or 0

#     summary = {
#         'total_paid': total_paid,
#         # 'total_pending': total_pending,
#         'total_orders': total_orders,
#     }

#     # 
#     years = settlements.dates('week_start', 'year')

#     # Pagination
#     paginator = Paginator(settlements, 10)
#     page_number = request.GET.get('page')
#     page_obj = paginator.get_page(page_number)
    
#     context = {
#         'page_obj': page_obj,
#         'summary': summary,
#         'years': years,
#         'current_year': year,
#         'producer': producer,
#     }
    
#     return render(request, 'payments/payment_history.html', context)

#     pass

# @login_required
# @producer_required
# def settlement_detail(request, settlement_id):
#     '''
    
#     '''
#     producer = request.user.producer_profile
    
#     settlement = get_object_or_404(
#         PaymentSettlement,
#         id=settlement_id,
#         producer=producer
#     )
    
#     # Get orders in this settlement
#     orders = settlement.orders.select_related(
#         'order_producer__payment__user'
#     ).all()
    
#     context = {
#         'settlement': settlement,
#         'orders': orders,
#         'producer': producer,
#     }
    
#     return render(request, 'payments/settlement_detail.html', context)
#     pass

@login_required
@producer_required
def download_settlement_csv(request, settlement_id):
    '''

    '''
    pass

@login_required
@producer_required
def download_settlement_pdf(request, settlement_id):
    '''
    
    '''
    pass