from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime
from decimal import Decimal
import csv
import io
import json
import logging

from django.conf import settings

from payments.models import PaymentSettlement, SettlementOrder
from mainApp.models import ProducerProfile
from orders.models import OrderProducer

logger = logging.getLogger(__name__)

@shared_task
def process_weekly_settlements():
    '''
    Task to create the weekly settlements for all producers
    Runs weekly via celery beat

    running this task in the middle week still contrains it to the current period 
    (Monday 00:00 to Sunday 11:59)
    '''

    now = timezone.now()
    day_since_monday = now.weekday()

    week_start = (now - timedelta(days=day_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = (now+ timedelta(days=6)).replace(
        hour=23, minute=59, second=59, microsecond=999999
    )

    producers_with_orders = OrderProducer.objects.filter(
        order_status='delivered',
        completed_at__range=[week_start,week_end],
        is_settled=False
    ).values_list('producer', flat=True).distinct()

    results = []
    for producer_id in producers_with_orders:
        try:
            result = process_producer_settlement.delay(producer_id, week_start, week_end)
            result.append({'producer_id': producer_id, 'task_id': result.id})
        except Exception as e:
            logger.error(f'error occur in process_weekly_settlements: {e}')

        return results

@shared_task
def process_producer_settlement(producer_id, week_start, week_end):
    '''
    process the single settlement for a producer
    '''

    try:
        producer = ProducerProfile.objects.get(id=producer_id)

        week_start_date = week_start.date() if hasattr(week_start, 'date') else week_start
        week_end_date = week_end.date() if hasattr(week_end, 'date') else week_end

        settlement, created = PaymentSettlement.objects.get_or_create(
            producer=producer,
            week_start=week_start_date,
            week_end=week_end_date,
        )

        if created:
            logger.info(f"Created new settlement for {producer.business_name}")
        else:
            logger.info(f"Found existing settlement #{settlement.id} for {producer.business_name}")
        
        completed_orders = OrderProducer.objects.filter(
            producer=producer,
            order_status='delivered',
            completed_at__range=[week_start, week_end],
            is_settled = False,
        ).select_related('payment', 'payment__user')

        if not completed_orders.exists():
            logger.info(f"No new completed orders for {producer.business_name} in this period")
            return {
                'status': 'no_orders',
                'producer': producer.business_name,
                'settlement': settlement.id if not created else None
            }
        
        with transaction.atomic():
            # Calculate totals
            total_orders = completed_orders.count()
            total_subtotal = sum(order.producer_subtotal for order in completed_orders)
            total_commission = sum(order.commission for order in completed_orders)
            total_payout = sum(order.producer_payout for order in completed_orders)
            
            # we do not consider stripe service fee which is
            # 1.5% + 20p for local uk cards
            
            settlement.total_orders += total_orders
            settlement.total_subtotal += total_subtotal
            settlement.total_commission += total_commission
            settlement.total_payout += total_payout
            settlement.settlement_status = 'processing'
            settlement.processed_at = timezone.now()
            
            # Create settlement order records and mark orders as settled
            for order in completed_orders:
                SettlementOrder.objects.create(
                    settlement=settlement,
                    order_producer=order,

                    order_id=order.id,
                    order_created_at=order.created_at,
                    order_completed_at=order.completed_at,
                    customer_name=order.payment.user.get_full_name(), #or order.payment.user.username,
                    customer_postcode=order.payment.shipping_address_id.post_code, # fetch order postcode. 

                    order_subtotal=order.producer_subtotal,
                    order_commission=order.commission,
                    order_payout=order.producer_payout,
                )
                
                # Mark order as settled
                order.is_settled = True
                order.settled_at = timezone.now()
                order.settlement_id = settlement.id
                order.save()
            
            # Generate settlement 
            # use the function below (i haven't test this but i suspect it wont work,
            # cuz i wrap it in a transaction.atomic)
            # generate_settlement_report.delay(settlement.id)
            
            # For sandbox: mark as pending (manual payout)
            # settlement.settlement_status = 'processing'
            # settlement.notes = bla bla (if manual or what not)

            settlement.save()
            
            logger.info(f"Added {total_orders} orders to settlement #{settlement.id} for {producer.business_name}")
            
            return {
                'status': 'success',
                'settlement_id': settlement.id,
                'producer': producer.business_name,
                'total_payout': str(total_payout),
            }
            
    except Exception as e:
        logger.error(f"Failed to process settlement for producer {producer_id}: {e}", exc_info=True)
        raise



# if we decide to use the generate csv and store to db option
@shared_task
def generate_settlement_report(settlement_id):
    """
    Generate CSV report for a settlement
    """
    try:
        settlement = PaymentSettlement.objects.get(id=settlement_id)
        
        # Get all orders in this settlement
        orders = settlement.orders.select_related('order_producer__payment__user').all()
        
        # Generate CSV
        csv_output = io.StringIO()
        csv_writer = csv.writer(csv_output)
        
        # Write headers
        csv_writer.writerow([
            'Order ID', 'Order Date', 'Customer Name', 'Customer Postcode',
            'Delivery Date', 'Subtotal (£)', 'Commission (£)', 'Payout (£)'
        ])
        
        # Write rows
        for order in orders:
            csv_writer.writerow([
                order.order_id,
                order.order_created_at.strftime('%Y-%m-%d'),
                order.customer_name,
                order.customer_postcode,
                order.completed_at.strftime('%Y-%m-%d') if order.completed_at else '',
                f"{order.order_subtotal:.2f}",
                f"{order.order_commission:.2f}",
                f"{order.order_payout:.2f}"
            ])
        
        # Add summary rows
        csv_writer.writerow([])
        csv_writer.writerow(['SUMMARY', '', '', '', '', '', '', ''])
        csv_writer.writerow(['Total Orders', settlement.total_orders])
        csv_writer.writerow(['Total Subtotal', '', f"£{settlement.total_subtotal:.2f}"])
        csv_writer.writerow(['Total Commission', '', f"£{settlement.total_commission:.2f}"])
        csv_writer.writerow(['Stripe Fees (est.)', '', f"£{settlement.total_stripe_fees:.2f}"])
        csv_writer.writerow(['Platform Revenue', '', f"£{settlement.net_platform_revenue:.2f}"])
        csv_writer.writerow(['Total Payout', '', f"£{settlement.total_payout:.2f}"])
        
        # Store CSV in settlement (you can save to file storage)
        settlement.csv_report = csv_output.getvalue()  # Add this field to model
        
        logger.info(f"Generated CSV report for settlement {settlement_id}")
        
        return {'settlement_id': settlement_id, 'csv_generated': True}
        
    except Exception as e:
        logger.error(f"Failed to generate report for settlement {settlement_id}: {e}")
        raise