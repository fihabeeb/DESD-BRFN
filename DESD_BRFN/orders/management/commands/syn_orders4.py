
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
import numpy as np
from decimal import Decimal
from collections import defaultdict
from django.db import transaction

from mainApp.models import CustomerProfile, Address
from products.models import Product
from orders.models import OrderPayment, OrderProducer, OrderItem

# Add this to your command file (above the Command class)
from collections import defaultdict
import random

DEFAULT_SEED = 42

# Category-based co-purchase relationships
CATEGORY_CO_PURCHASE = {
    # Dairy pairs well with many things
    'dairy': {
        'coffee': 0.4,      # Milk in coffee
        'tea': 0.3,          # Milk in tea
        'grains': 0.35,      # Cheese with pasta/bread
        'fruits': 0.2,       # Yogurt with berries
        'Herbs Spices': 0.15 # Cheese with herbs
    },
    
    # Meat pairs with vegetables and herbs
    'meat': {
        'vegetables': 0.5,   # Meat with veggies
        'Herbs Spices': 0.3, # Seasoning for meat
        'grains': 0.25,      # Meat with rice/pasta
        'mushrooms': 0.2     # Meat with mushrooms
    },
    
    # Vegetables pair with many things
    'vegetables': {
        'meat': 0.4,         # Veggies with meat
        'dairy': 0.25,       # Veggies with cheese
        'Herbs Spices': 0.35, # Seasoning for veggies
        'grains': 0.2        # Veggies with rice/pasta
    },
    
    # Fruits pair with dairy and honey
    'fruits': {
        'dairy': 0.4,        # Fruit with yogurt/cream
        'Honey Bee': 0.3,    # Fruit with honey
        'snacks': 0.2,       # Dried fruits
        'beverages': 0.25    # Fruit juices
    },
    
    # Grains (bread, pasta, rice) pairings
    'grains': {
        'dairy': 0.35,       # Pasta with cheese, bread with butter
        'meat': 0.3,         # Rice with chicken
        'vegetables': 0.3,   # Pasta with veggies
        'preserves': 0.2,    # Bread with jam
        'Herbs Spices': 0.15  # Seasoning
    },
    
    # Beverages (tea, coffee, juice)
    'beverages': {
        'dairy': 0.3,        # Milk in coffee/tea
        'Honey Bee': 0.35,   # Honey in tea
        'fruits': 0.2,       # Fruit juice combinations
        'Herbs Spices': 0.15  # Herbal teas
    },
    
    # Herbs & Spices - almost always paired
    'Herbs Spices': {
        'meat': 0.5,         # Seasoning meat
        'vegetables': 0.5,   # Seasoning veggies
        'grains': 0.3,       # Seasoning rice/pasta
        'mushrooms': 0.3,    # Seasoning mushrooms
        'dairy': 0.15        # Herbed cheese
    },
    
    # Mushrooms pairings
    'mushrooms': {
        'meat': 0.35,        # Mushrooms with meat
        'vegetables': 0.35,  # Mushrooms in veggie dishes
        'grains': 0.25,      # Mushrooms with rice/pasta
        'dairy': 0.2         # Creamy mushroom dishes
    },
    
    # Preserves (jams, pickles, chutneys)
    'preserves': {
        'grains': 0.4,       # Jam on bread
        'dairy': 0.3,        # Jam with cheese/yogurt
        'meat': 0.2,         # Chutney with meat
        'snacks': 0.15       # Preserves with crackers
    },
    
    # Honey & Bee products
    'Honey Bee': {
        'beverages': 0.4,    # Honey in tea
        'dairy': 0.3,        # Honey with yogurt
        'fruits': 0.25,      # Honey with fruit
        'snacks': 0.2        # Honey on snacks
    },
    
    # Snacks
    'snacks': {
        'beverages': 0.35,   # Snacks with drinks
        'fruits': 0.25,      # Nuts with dried fruit
        'dairy': 0.2,        # Cheese with nuts
        'preserves': 0.15    # Preserves with crackers
    }
}

# Specific product name patterns for stronger co-purchase bonds
SPECIFIC_PAIRINGS = {
    # Coffee-related
    'Coffee': ['Milk', 'Cream', 'Sugar', 'Honey'],
    'Tea': ['Honey', 'Lemon', 'Milk', 'Sugar'],
    
    # Pasta-related
    'Spaghetti': ['Parmesan', 'Tomato Sauce', 'Basil', 'Garlic'],
    'Penne': ['Parmesan', 'Tomato Sauce', 'Pesto'],
    'Fresh Pasta': ['Parmesan', 'Basil', 'Tomato Sauce'],
    
    # Bread-related
    'Sourdough': ['Butter', 'Jam', 'Honey'],
    'Baguette': ['Butter', 'Cheese', 'Olive Oil'],
    
    # Rice-related
    'Basmati Rice': ['Chicken', 'Vegetables', 'Curry'],
    'Brown Rice': ['Vegetables', 'Chicken', 'Mushrooms'],
    
    # Breakfast items
    'Granola': ['Yogurt', 'Honey', 'Berries'],
    'Oats': ['Milk', 'Honey', 'Berries'],
    
    # Salad items
    'Lettuce': ['Tomatoes', 'Cucumber', 'Olive Oil'],
    'Spinach': ['Feta', 'Walnuts', 'Strawberries'],
    
    # Cheese pairings
    'Cheddar': ['Bread', 'Apple', 'Chutney'],
    'Brie': ['Baguette', 'Grapes', 'Crackers'],
    'Goat Cheese': ['Salad', 'Beetroot', 'Walnuts'],
    
    # Meat pairings
    'Chicken Breast': ['Rosemary', 'Garlic', 'Lemon'],
    'Minced Beef': ['Pasta', 'Tomato Sauce', 'Onions'],
    'Lamb Chops': ['Rosemary', 'Garlic', 'Mint'],
    
    # Dessert items
    'Strawberries': ['Cream', 'Chocolate', 'Sugar'],
    'Apples': ['Cinnamon', 'Sugar', 'Butter'],
}

def get_co_purchase_products(product, all_products, product_by_category):
    """
    Get co-purchase recommendations for a product based on:
    1. Specific product pairings (strongest)
    2. Category-based pairings (medium strength)
    3. Random similar products (weakest)
    """
    recommendations = []
    
    # 1. Check specific pairings first
    product_name = product.name
    for key, pairings in SPECIFIC_PAIRINGS.items():
        if key in product_name or product_name in key:
            # Find matching products
            for pairing_name in pairings:
                matched = get_product_by_name(all_products, pairing_name)
                if matched and matched.id != product.id:
                    recommendations.append(matched)
    
    # 2. Category-based pairings
    if product.category and product.category.name.lower() in CATEGORY_CO_PURCHASE:
        category = product.category.name.lower()
        possible_categories = CATEGORY_CO_PURCHASE[category]
        
        # Weighted selection based on probability
        for target_cat, probability in possible_categories.items():
            if random.random() < probability and target_cat in product_by_category:
                if product_by_category[target_cat]:
                    # Pick a random product from that category
                    candidates = [p for p in product_by_category[target_cat] if p.id != product.id]
                    if candidates:
                        recommendations.append(random.choice(candidates))
    
    # Remove duplicates while preserving order
    seen = set()
    unique_recs = []
    for rec in recommendations:
        if rec.id not in seen:
            seen.add(rec.id)
            unique_recs.append(rec)
    
    return unique_recs[:3]  # Return up to 3 recommendations

def get_product_by_name(products, name):
    for p in products:
        if p.name == name:
            return p
    return None


class Command(BaseCommand):
    help = "Generate realistic synthetic orders without artificial patterns"

    def add_arguments(self, parser):
        parser.add_argument(
            '--seed',
            type=int,
            default=DEFAULT_SEED,
            help='Random seed for reproducible data generation (default: 42)'
        )

    def handle(self, *args, **kwargs):
        seed = kwargs.get('seed', DEFAULT_SEED)
        random.seed(seed)
        np.random.seed(seed)
        customers = list(CustomerProfile.objects.all().order_by('id'))
        products = list(Product.objects.filter(availability='available').order_by('id'))
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

            # --- User-specific behaviour ---
            favorite_products = random.sample(products, k=min(15, len(products)))

            preferred_categories = random.sample(
                list(product_by_category.keys()), 
                k=min(3, len(product_by_category))
            )

            staples = random.sample(products, k=min(5, len(products)))
            
            # Each customer has natural preferences (but NOT predefined patterns)
            # These emerge from their purchase history, not forced patterns
            num_orders = random.randint(80,130)

            timestamps = self.add_realistic_timing(num_orders)
            orders_for_customer = []
            for idx, created_at in enumerate(timestamps):
            
                # Create order
                order = OrderPayment.objects.create(
                    user=user,
                    payment_status='paid',
                    total_amount=Decimal("0.00"),
                    shipping_address_id=user.default_address,
                    created_at=created_at,
                )
                
                # Basket size follows power law distribution (realistic)
                basket_size = self.weighted_basket_size()
                selected_products = []

                # --- Phase 1: core selection (respects basket_size) ---
                for i in range(basket_size):
                    selection_method = random.random()
                    
                    if selection_method < 0.35 and customer_history[customer.id]: #.7
                        product = random.choice(customer_history[customer.id])
                    elif selection_method < 0.8:
                        if random.random() < 0.7:
                            product = random.choice(favorite_products)
                        else:
                            category = random.choice(preferred_categories)
                            product = random.choice(product_by_category[category]) \
                                if product_by_category[category] else random.choice(products)
                    else:
                        # Exploration
                        product = random.choice(products)
                    
                    selected_products.append(product)
                    customer_history[customer.id].append(product)


                product_by_name = {p.name: p for p in products}                
                # phase 2
                co_purchase_additions = []
                for product in selected_products:
                    # 60% chance to add a co-purchase item
                    if random.random() < 0.6:
                        # Get recommendations based on product relationships
                        recommendations = get_co_purchase_products(
                            product, products, product_by_category
                        )
                        
                        # Add 1-2 recommendations if available
                        if recommendations:
                            num_to_add = random.randint(1, min(2, len(recommendations)))
                            co_purchase_additions.extend(random.sample(recommendations, num_to_add))

                selected_products.extend(co_purchase_additions)

                if random.random() < 0.3:  # 30% of orders get a seasonal pairing
                    seasonal_pairs = [
                        ('Pumpkin', ['Cinnamon', 'Nutmeg', 'Cloves']),
                        ('Strawberries', ['Cream', 'Sugar']),
                        ('Turkey', ['Sage', 'Thyme', 'Rosemary']),
                        ('Apple', ['Cinnamon', 'Sugar']),
                    ]
                    
                    for main_item, seasonal_items in seasonal_pairs:
                        main_product = get_product_by_name(products, main_item)
                        if main_product and main_product in selected_products:
                            for seasonal_item in seasonal_items:
                                seasonal_product = get_product_by_name(products, seasonal_item)
                                if seasonal_product and random.random() < 0.5:
                                    selected_products.append(seasonal_product)

                # Staple top-up: only if basket is genuinely small, and add at most 1
                if len(selected_products) < 3 and random.random() < 0.5:
                    selected_products.append(random.choice(staples))

                # Deduplicate while preserving order
                seen = set()
                unique_products = []
                for p in selected_products:
                    if p.id not in seen:
                        seen.add(p.id)
                        unique_products.append(p)
                
                # Process order (deduplicate within same order)
                producer_map = {}
                order_total = Decimal("0.00")

                selected_products = list(set(selected_products))
                random.shuffle(selected_products)
                for product in set(selected_products):  # Use set to avoid duplicates in same order
                    producer = product.producer
                    if not producer:
                        continue

                    # random completion date since order is created
                    days_since_order_created_at=random.randint(4,10)
                    completed_at= (created_at + timedelta(days=days_since_order_created_at))
                    
                    if producer.id not in producer_map:
                        producer_map[producer.id] = OrderProducer.objects.create(
                            payment=order,
                            producer=producer,
                            producer_subtotal=Decimal("0.00"),
                            order_status='delivered',
                            created_at=created_at,
                            completed_at=completed_at
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
                
                # Store order info for potential future use
                orders_for_customer.append({
                    'order': order,
                    'timestamp': created_at,
                    'basket_size': basket_size
                })
                # except Exception as e:
                #     self.stdout.write(self.style.ERROR(f"{e}"))
            
            if customers.index(customer) % 10 == 0:
                self.stdout.write(f'Processed {customers.index(customer)}/{len(customers)} customers...')
        
        # Print statistics
        self.stdout.write(self.style.SUCCESS(f'Generated {total_orders} orders for {len(customers)} customers'))
        self.print_statistics(customer_history, products)

        return
    
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


    def add_realistic_timing(self, num_orders):
        """Generate realistic purchase timing with patterns (wrap around if exceed present)"""
        timestamps = []
        
        shopping_pattern = random.choice(["weekly", "biweekly", "monthly"])
        
        # Start with a random past date
        start_date = timezone.now() - timedelta(days=random.randint(30, 90))
        current_date = start_date
        
        for i in range(num_orders):
            if shopping_pattern == "weekly":
                base_gap = random.randint(5, 9)
            elif shopping_pattern == "biweekly":
                base_gap = random.randint(10, 18)
            else:
                base_gap = random.randint(25, 35)
            
            gap_days = base_gap + random.randint(-2, 2)
            current_date += timedelta(days=gap_days)
            
            # If we reach the present, wrap around to the past
            if current_date > timezone.now():
                # Start a new cycle from the original start date
                current_date = start_date + timedelta(days=random.randint(1, 30))
            
            # Apply weekend bias
            if self.should_keep_purchase(current_date):
                adjusted_ts = current_date
            else:
                adjusted_ts = self.adjust_to_weekday(current_date)
            
            if adjusted_ts not in timestamps:
                timestamps.append(adjusted_ts)
            # else: skip duplicate timestamp
        
        timestamps.sort()
        return timestamps
    
    def should_keep_purchase(self, timestamp):
        """Decide whether to keep a purchase based on weekend bias"""
        is_weekend = timestamp.weekday() >= 5  # 5=Saturday, 6=Sunday
        
        if is_weekend:
            # Weekend purchases: 70% chance to keep, 30% chance to move to weekday
            return random.random() < 0.7
        else:
            # Weekday purchases: 90% chance to keep
            return random.random() < 0.9
    
    def adjust_to_weekday(self, timestamp):
        """Move a weekend purchase to the nearest weekday"""
        weekday = timestamp.weekday()
        
        if weekday == 5:  # Saturday
            # 50% chance to move to Friday, 50% to Monday
            if random.random() < 0.5:
                return timestamp - timedelta(days=1)  # Friday
            else:
                return timestamp + timedelta(days=2)  # Monday
        elif weekday == 6:  # Sunday
            # 50% chance to move to Friday, 50% to Monday
            if random.random() < 0.5:
                return timestamp - timedelta(days=2)  # Friday
            else:
                return timestamp + timedelta(days=1)  # Monday
        
        return timestamp  # Already a weekday