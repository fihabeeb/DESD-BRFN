from django.utils import timezone
from decimal import Decimal
from mainApp.models import RegularUser, ProducerProfile
from orders.models import OrderProducer
from django.db import models
from datetime import date
from payments.utils import calculate_tax_year

# dont create settlement until order is completed.
# this wont ruin the db integrity when referencing orderproducer.

class PaymentSettlement(models.Model):
    '''
    weekly settlement tc-12 for producer
    This table is managing the period and amount for that week or tax year. 
    '''

    SETTLEMENT_STATUS_CHOICE = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),

        ('failed', 'Failed'),
    ]

    producer = models.ForeignKey(
        ProducerProfile,
        on_delete=models.PROTECT,
        related_name='paymenet_settlements'
    )

    # period
    week_start = models.DateField()
    week_end = models.DateField()
    tax_year = models.CharField(max_length=30, blank=True, null=True, default=None, db_index=True)

    # finanacial summary
    total_orders = models.PositiveBigIntegerField(default=0)
    total_subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    total_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # settlements details
    settlement_status = models.CharField(max_length=20, choices=SETTLEMENT_STATUS_CHOICE, default='pending')
    payment_reference = models.CharField()
    
    paid_at = models.DateTimeField(null=True, blank=True)


    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True) # when completed

    '''
    table properties
    '''
    class Meta:
        unique_together = ['producer', 'week_start', 'week_end']
        ordering = ['-week_start']

    def __str__(self):
        return f"Settlement {self.producer.business_name} - Week of {self.week_start}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate tax year before saving
        if not self.tax_year and self.week_end:
            self.tax_year = calculate_tax_year(self.week_end)
        super().save(*args, **kwargs)
    
    '''
    Properties
    '''
    @property
    def week_display(self):
        return f"{self.week_start.strftime('%d %b %Y')} - {self.week_end.strftime('%d %b %Y')}"
    
    @property
    def tax_year_start(self):
        '''
        Get the tax year this settlement falls in
        The UK tax year starts on April 6 and ends on April 5
        '''
        today = self.week_start
        year = today.year

        tax_year_start = date(year, 4, 6) 
        if today < tax_year_start:
            tax_year_start = date(year -1, 4 ,6)

        return tax_year_start
    
    @property
    def tax_year_end(self):
        """Get the end date of the current UK tax year"""
        return date(self.tax_year_start.year + 1, 4, 5)
    
    @property
    def tax_year_display(self):
        """Display tax year as '2024/2025'"""
        start_year = self.tax_year_start.year
        return f"{start_year}/{start_year + 1}"
    
    """
    class method
    """
    @classmethod
    def get_available_tax_years(cls, producer=None):
        """Get distinct tax years from settlements"""
        queryset = cls.objects.all()
        if producer:
            queryset = queryset.filter(producer=producer)
        return queryset.values_list('tax_year', flat=True).distinct().order_by('-tax_year')

    '''
    Functions
    '''    
    def mark_as_processing(self):
        self.settlement_status='processing'
        self.save()
    
    def mark_as_completed(self):
        self.settlement_status='completed'
        self.paid_at = timezone.now()
        self.save()

    
    
    def generate_csv_report(self):
        """
        generate CSV report
        could potentially store csv data in db but idk
        """
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'Settlement ID', self.id
        ])
        writer.writerow([
            'Producer', self.producer.business_name
        ])
        writer.writerow([
            'Period', f"{self.week_start} to {self.week_end}"
        ])
        writer.writerow([])
        
        writer.writerow([
            'Order ID', 'Date', 'Customer', 'Subtotal', 'Commission', 'Payout'
        ])
        
        for order in self.get_orders_queryset():
            writer.writerow([
                order.id,
                order.created_at.strftime('%Y-%m-%d'),
                order.payment.user.get_full_name() or order.payment.user.username,
                f"{order.producer_subtotal:.2f}",
                f"{order.commission:.2f}",
                f"{order.producer_payout:.2f}"
            ])
        
        writer.writerow([])
        writer.writerow(['TOTAL', '', '', '', '', f"£{self.total_payout:.2f}"])
        
        return output.getvalue()
    

class SettlementOrder(models.Model):
    '''
    Include the order(s) to the period of settlement
    all of this should be snapshot at the start of creation.
    '''

    settlement = models.ForeignKey(
        PaymentSettlement,
        on_delete=models.CASCADE,
        related_name='orders'
    )

    order_producer = models.ForeignKey(
        OrderProducer,
        on_delete=models.PROTECT,
        related_name='settlement_records'
    )

    # snapshot order details / analytical details
    order_id = models.IntegerField()
    order_created_at = models.DateTimeField()
    order_completed_at = models.DateTimeField()
    customer_name = models.CharField(max_length=255, blank=True)
    customer_postcode = models.CharField(max_length=20, blank=True) # postcode for local council tax bla bla

    # financial snapshot
    order_subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    order_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    order_payout = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # tracking
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['settlement', 'order_producer']