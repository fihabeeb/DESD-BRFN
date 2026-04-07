# recommendation/management/commands/generate_synthetic_orders_enhanced.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
import numpy as np
from decimal import Decimal
from collections import defaultdict

from mainApp.models import CustomerProfile
from products.models import Product
from orders.models import OrderPayment, OrderProducer, OrderItem


class Command(BaseCommand):
    help = "Generate enhanced synthetic order data with realistic purchase patterns"

    def handle(self, *args, **kwargs):
        customers = list(CustomerProfile.objects.all())
        products = list(Product.objects.filter(availability='available'))
        
        if len(customers) < 50:
            self.stdout.write(self.style.WARNING(f'Only {len(customers)} customers. Creating more...'))
            # You'd create more customers here
        
        if len(products) < 100:
            self.stdout.write(self.style.ERROR(f'Need at least 100 products, found {len(products)}. Run seed_products_enhanced first.'))
            return
        
        # Define product categories for pattern generation
        product_categories = defaultdict(list)
        for product in products:
            product_categories[product.category.name.lower()].append(product)
        
        # Define purchase patterns (sequence of categories)
        purchase_patterns = [
            # Breakfast pattern
            ['dairy', 'bakery', 'fruits', 'dairy'],
            # Cooking pattern
            ['vegetables', 'meat', 'herbs_spices', 'vegetables'],
            # Healthy snacking
            ['fruits', 'snacks', 'fruits', 'dairy'],
            # Baking pattern
            ['bakery', 'dairy', 'fruits', 'bakery'],
            # Weekend cooking
            ['meat', 'vegetables', 'herbs_spices', 'beverages'],
            # Quick meals
            ['vegetables', 'dairy', 'bakery', 'fruits'],
            # Gourmet cooking
            ['mushrooms', 'meat', 'herbs_spices', 'beverages'],
            # Family meals
            ['vegetables', 'meat', 'dairy', 'vegetables', 'bakery'],
        ]
        
        # Define product associations (products often bought together)
        product_associations = self.build_product_associations(products)
        
        total_orders = 0
        
        for customer in customers:
            user = customer.user
            
            # Generate 20-50 orders per customer for better sequences
            num_orders = random.randint(20, 50)
            
            # Each customer has favorite categories
            favorite_categories = random.sample(list(product_categories.keys()), 
                                               min(3, len(product_categories.keys())))
            
            # Each customer has favorite products
            favorite_products = []
            for cat in favorite_categories:
                if product_categories[cat]:
                    favorite_products.extend(random.sample(product_categories[cat], 
                                                          min(5, len(product_categories[cat]))))
            
            # Track purchase history for this customer
            purchase_history = []
            
            for order_num in range(num_orders):
                # Create order with realistic timing (more recent orders have higher probability)
                if order_num < num_orders * 0.3:  # 30% recent orders
                    days_ago = random.randint(0, 7)
                elif order_num < num_orders * 0.7:  # 40% medium age
                    days_ago = random.randint(8, 30)
                else:  # 30% older orders
                    days_ago = random.randint(31, 90)
                
                created_at = timezone.now() - timedelta(days=days_ago)
                
                order = OrderPayment.objects.create(
                    # customer=customer,
                    user=user,
                    payment_status='paid',
                    total_amount=Decimal("0.00"),
                    created_at=created_at
                )
                
                order_total = Decimal("0.00")
                producer_map = {}
                
                # Determine number of items (basket size)
                # Larger baskets on weekends
                is_weekend = created_at.weekday() >= 5
                basket_size = random.randint(2, 8) if is_weekend else random.randint(1, 5)
                
                selected_products = []
                
                # Choose products based on patterns
                for i in range(basket_size):
                    # Use different strategies for product selection
                    if i == 0 and purchase_history:
                        # First item: sometimes repeat last purchase
                        if random.random() < 0.4:
                            last_product = purchase_history[-1]
                            if last_product in products:
                                selected_products.append(last_product)
                                continue
                    
                    # Use purchase patterns
                    if purchase_history and random.random() < 0.6:
                        # Get category of last purchase
                        last_product = purchase_history[-1]
                        if last_product in products:
                            last_category = last_product.category.name.lower()
                            # Find pattern that matches
                            for pattern in purchase_patterns:
                                if last_category in pattern:
                                    next_idx = (pattern.index(last_category) + 1) % len(pattern)
                                    next_category = pattern[next_idx]
                                    if product_categories.get(next_category):
                                        product = random.choice(product_categories[next_category])
                                        selected_products.append(product)
                                        break
                            else:
                                # Fallback to favorite category
                                category = random.choice(favorite_categories)
                                if product_categories.get(category):
                                    product = random.choice(product_categories[category])
                                    selected_products.append(product)
                        else:
                            # Random from favorite categories
                            category = random.choice(favorite_categories)
                            if product_categories.get(category):
                                product = random.choice(product_categories[category])
                                selected_products.append(product)
                    else:
                        # Random selection with bias towards favorites
                        if random.random() < 0.7 and favorite_products:
                            product = random.choice(favorite_products)
                        else:
                            product = random.choice(products)
                        selected_products.append(product)
                
                # Add complementary products (often bought together)
                final_products = []
                for product in selected_products:
                    final_products.append(product)
                    
                    # 30% chance to add a complementary product
                    if random.random() < 0.3 and product.id in product_associations:
                        complementary = random.choice(product_associations[product.id])
                        if complementary not in final_products:
                            final_products.append(complementary)
                
                # Create order items
                for product in final_products:
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
                    
                    # Quantity based on product type
                    if product.unit in ['kg', 'litre']:
                        quantity = random.choice([1, 2, 3, 5])
                    else:
                        quantity = random.randint(1, 4)
                    
                    price = product.price
                    
                    item = OrderItem.objects.create(
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
                    purchase_history.append(product)
                
                for po in producer_map.values():
                    po.save()
                
                order.total_amount = order_total
                order.save()
                total_orders += 1
            
            # Print progress
            if customers.index(customer) % 10 == 0:
                self.stdout.write(f'Processed {customers.index(customer)}/{len(customers)} customers...')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully generated {total_orders} orders for {len(customers)} customers'))

    def build_product_associations(self, products):
        """Build product associations based on categories and seasons"""
        associations = defaultdict(list)
        
        # Group products by category
        by_category = defaultdict(list)
        for product in products:
            by_category[product.category.name.lower()].append(product)
        
        # Create associations within same category
        for category, prods in by_category.items():
            for i, prod in enumerate(prods):
                # Associate with other products in same category
                others = [p for j, p in enumerate(prods) if j != i]
                if others:
                    associations[prod.id].extend(random.sample(others, min(3, len(others))))
        
        # Cross-category associations (e.g., strawberries + cream)
        complementary_pairs = [
            ('fruits', 'dairy'), ('vegetables', 'meat'), ('bakery', 'dairy'),
            ('herbs_spices', 'vegetables'), ('fruits', 'bakery'), ('meat', 'herbs_spices')
        ]
        
        for cat1, cat2 in complementary_pairs:
            if by_category.get(cat1) and by_category.get(cat2):
                for prod1 in by_category[cat1][:20]:  # Limit for performance
                    prod2 = random.choice(by_category[cat2])
                    associations[prod1.id].append(prod2)
                    associations[prod2.id].append(prod1)
        
        return associations