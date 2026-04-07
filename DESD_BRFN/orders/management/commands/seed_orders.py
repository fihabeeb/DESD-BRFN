# orders/management/commands/seed_orders.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
from decimal import Decimal

from orders.models import Order, OrderItem
from mainApp.models import RegularUser, CustomerProfile, Address
from products.models import Product, ProductCategory


class Command(BaseCommand):
    help = 'Seed orders with mock data for testing'

    def handle(self, *args, **options):
        if Order.objects.exists():
            self.stdout.write('Orders already seeded, skipping.')
            return

        # Get customers with profiles
        customers = RegularUser.objects.filter(role='customer', customer_profile__isnull=False)
        if not customers.exists():
            self.stdout.write(self.style.ERROR('No customers found. Run seed_customers first.'))
            return

        # Get products
        products = list(Product.objects.all())
        if len(products) < 5:
            self.stdout.write(self.style.ERROR(f'Need at least 5 products, found {len(products)}. Run seed_products first.'))
            return

        # Get addresses for customers
        addresses = Address.objects.filter(address_type='home', is_default=True)
        
        # Status weights (for realistic distribution)
        status_weights = {
            'delivered': 0.4,
            'confirmed': 0.2,
            'processing': 0.15,
            'ready': 0.1,
            'pending': 0.1,
            'cancelled': 0.05,
        }
        
        # Statuses with their realistic date ranges (in days)
        status_date_ranges = {
            'delivered': (30, 1),
            'confirmed': (15, 3),
            'processing': (7, 1),
            'ready': (5, 0),
            'pending': (2, 0),
            'cancelled': (20, 1),
        }
        
        self.stdout.write(self.style.SUCCESS('Creating mock orders...'))
        
        created_count = 0
        status_counts = {status: 0 for status in status_weights.keys()}
        
        # Create 20-30 orders
        num_orders = random.randint(20, 30)
        
        for i in range(num_orders):
            # Select random customer
            customer = random.choice(customers)
            
            # Select random address
            customer_addresses = customer.addresses.filter(is_default=True)
            address = customer_addresses.first() or addresses.first()
            
            # Determine order status based on weights
            status = random.choices(
                list(status_weights.keys()),
                weights=list(status_weights.values())
            )[0]
            status_counts[status] += 1
            
            # Determine order date based on status
            days_range = status_date_ranges[status]
            days_ago = random.randint(days_range[1], days_range[0])
            order_date = timezone.now() - timedelta(days=days_ago)
            
            # Determine number of items
            num_items = random.randint(1, 5)
            selected_products = random.sample(products, min(num_items, len(products)))
            
            # Calculate totals
            subtotal = Decimal('0.00')
            items_data = []
            
            for product in selected_products:
                quantity = random.randint(1, 3)
                item_total = product.price * quantity
                subtotal += item_total
                items_data.append({
                    'product': product,
                    'quantity': quantity,
                })
            
            commission = subtotal * Decimal('0.05')
            total_amount = subtotal + commission
            
            # Create order
            order = Order.objects.create(
                customer=customer.customer_profile,
                user=customer,
                stripe_session_id=f"seed_session_{i}_{random.randint(1000, 9999)}",
                stripe_payment_intent_id=f"seed_payment_{i}_{random.randint(1000, 9999)}",
                status=status,
                subtotal=subtotal,
                commission=commission,
                total_amount=total_amount,
                shipping_address=address.full_address if address else "",
                shipping_address_id=address.id if address else None,
                delivery_date=order_date.date() + timedelta(days=random.randint(2, 5)),
                created_at=order_date,
            )
            
            # Create order items
            for item_data in items_data:
                product = item_data['product']
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    producer=product.producer,
                    product_name=product.name,
                    product_price=product.price,
                    quantity=item_data['quantity'],
                    unit=product.unit,
                )
            
            created_count += 1
            
            if (i + 1) % 10 == 0:
                self.stdout.write(f"  Created {i + 1} orders...")
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} orders!'))
        self.stdout.write(f"Order status distribution:")
        for status, count in status_counts.items():
            self.stdout.write(f"  {status}: {count} orders")