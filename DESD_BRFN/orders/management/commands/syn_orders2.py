# recommendation/management/commands/generate_realistic_orders.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
import numpy as np
from decimal import Decimal
from collections import defaultdict

from mainApp.models import CustomerProfile, Address
from products.models import Product
from orders.models import OrderPayment, OrderProducer, OrderItem


class Command(BaseCommand):
    help = "Generate realistic synthetic orders without artificial patterns"

    def handle(self, *args, **kwargs):
        customers = list(CustomerProfile.objects.all())
        products = list(Product.objects.filter(availability='available'))
        home_addresses = list(Address.objects.filter(
            address_type='home'
        ))
        
        if len(products) < 100:
            self.stdout.write(self.style.ERROR(f'Need at least 100 products, found {len(products)}. Run enhanced seed first.'))
            return
        
        # Build category mapping
        product_by_category = defaultdict(list)
        for product in products:
            product_by_category[product.category.name.lower()].append(product)
        
        # Track REAL purchase history per customer (to be used naturally)
        customer_history = defaultdict(list)
        
        total_orders = 0
        
        for customer in customers:
            user = customer.user

            # customer_addresses = list(user.addresses.filter(address_type='home'))
            
            # Each customer has natural preferences (but NOT predefined patterns)
            # These emerge from their purchase history, not forced patterns
            num_orders = random.randint(15, 40)
            
            for order_num in range(num_orders):
                # Random timing (no artificial recency bias)
                days_ago = random.randint(0, 90)
                created_at = timezone.now() - timedelta(days=days_ago)

                # selected_address = random.choice(customer_addresses) # probably only 1 address associated tho
                
                order = OrderPayment.objects.create(
                    # customer=customer,
                    user=user,
                    payment_status='paid',
                    total_amount=Decimal("0.00"),
                    shipping_address_id = user.default_address,
                    created_at=created_at
                )
                
                # Basket size follows power law distribution (realistic)
                # Most orders are 1-3 items, occasional larger orders
                basket_size = self.weighted_basket_size()
                
                selected_products = []
                
                for i in range(basket_size):
                    # Selection strategy WITHOUT artificial patterns
                    selection_method = random.random()
                    
                    if selection_method < 0.6 and customer_history[customer.id]:
                        # 60%: Choose from customer's history (repeat purchases)
                        # This naturally creates sequences without forcing patterns
                        product = random.choice(customer_history[customer.id])
                    elif selection_method < 0.8 and product_by_category:
                        # 20%: Explore new categories (random category)
                        category = random.choice(list(product_by_category.keys()))
                        if product_by_category[category]:
                            product = random.choice(product_by_category[category])
                        else:
                            product = random.choice(products)
                    else:
                        # 20%: Complete random exploration
                        product = random.choice(products)
                    
                    selected_products.append(product)
                    customer_history[customer.id].append(product)
                
                # Process order (deduplicate within same order)
                producer_map = {}
                order_total = Decimal("0.00")
                
                for product in set(selected_products):  # Use set to avoid duplicates in same order
                    producer = product.producer
                    if not producer:
                        continue
                    
                    if producer.id not in producer_map:
                        producer_map[producer.id] = OrderProducer.objects.create(
                            payment=order,
                            producer=producer,
                            producer_subtotal=Decimal("0.00"),
                            order_status='confirmed',
                        )
                    
                    producer_order = producer_map[producer.id]
                    
                    # Quantity based on product type (realistic)
                    quantity = self.get_realistic_quantity(product)
                    price = product.price
                    
                    OrderItem.objects.create(
                        producer_order=producer_order,
                        product=product,
                        product_name=product.name,
                        product_price=price,
                        quantity=quantity,
                        unit=product.unit
                    )
                    
                    line_total = price * quantity
                    order_total += line_total
                    producer_order.producer_subtotal += line_total
                
                for po in producer_map.values():
                    po.save()
                
                order.total_amount = order_total
                order.save()
                total_orders += 1
            
            if customers.index(customer) % 10 == 0:
                self.stdout.write(f'Processed {customers.index(customer)}/{len(customers)} customers...')
        
        # Print statistics
        self.stdout.write(self.style.SUCCESS(f'Generated {total_orders} orders for {len(customers)} customers'))
        self.print_statistics(customer_history, products)
    
    def weighted_basket_size(self):
        """Basket size follows realistic distribution (power law)"""
        # Most orders: 1-3 items, occasional: 4-6, rare: 7+
        r = random.random()
        if r < 0.5:
            return 1
        elif r < 0.75:
            return 2
        elif r < 0.9:
            return 3
        elif r < 0.97:
            return random.randint(4, 6)
        else:
            return random.randint(7, 10)
    
    def get_realistic_quantity(self, product):
        """Realistic quantities based on product type"""
        if product.unit == 'kg':
            return random.choice([1, 2, 3, 5])
        elif product.unit == 'litre':
            return random.choice([1, 2, 4])
        elif product.unit in ['each', 'bunch', 'pack', 'jar']:
            return random.randint(1, 4)
        else:
            return random.randint(1, 3)
    
    def print_statistics(self, customer_history, products):
        """Print dataset statistics"""
        all_purchases = []
        for history in customer_history.values():
            all_purchases.extend(history)
        
        unique_products_purchased = len(set(all_purchases))
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write("DATASET STATISTICS")
        self.stdout.write("="*50)
        self.stdout.write(f"Total customers: {len(customer_history)}")
        self.stdout.write(f"Total purchases: {len(all_purchases)}")
        self.stdout.write(f"Unique products purchased: {unique_products_purchased}/{len(products)}")
        self.stdout.write(f"Average purchases per customer: {len(all_purchases)/len(customer_history):.1f}")
        
        # Check sequence lengths
        seq_lengths = [len(hist) for hist in customer_history.values()]
        self.stdout.write(f"Average sequence length: {np.mean(seq_lengths):.1f}")
        self.stdout.write(f"Max sequence length: {max(seq_lengths)}")
        self.stdout.write(f"Min sequence length: {min(seq_lengths)}")