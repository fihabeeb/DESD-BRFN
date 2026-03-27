# products/management/commands/seed_products.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from products.models import Product, ProductCategory
from mainApp.models import ProducerProfile
import random


class Command(BaseCommand):
    help = 'Seed products with mock data'

    def handle(self, *args, **options):
        if Product.objects.exists():
            self.stdout.write('Products already seeded, skipping.')
            return

        # Get existing producers
        producers = list(ProducerProfile.objects.all())
        if len(producers) < 4:
            self.stdout.write(self.style.ERROR(f'Need at least 4 producers, found {len(producers)}. Create more producers first.'))
            return

        # Create categories
        categories = {
            # Main categories
            'fruits': ProductCategory.objects.create(
                name='Fruits', 
                slug='fruits', 
                description='Fresh seasonal fruits from local orchards', 
                order=1,
                is_active=True
            ),
            'vegetables': ProductCategory.objects.create(
                name='Vegetables', 
                slug='vegetables', 
                description='Fresh vegetables grown locally', 
                order=2,
                is_active=True
            ),
            'dairy': ProductCategory.objects.create(
                name='Dairy & Eggs', 
                slug='dairy-eggs', 
                description='Fresh dairy products and free-range eggs', 
                order=3,
                is_active=True
            ),
            'meat': ProductCategory.objects.create(
                name='Meat & Poultry', 
                slug='meat-poultry', 
                description='Ethically raised meat and poultry', 
                order=4,
                is_active=True
            ),
            'bakery': ProductCategory.objects.create(
                name='Bakery', 
                slug='bakery', 
                description='Freshly baked bread and pastries', 
                order=5,
                is_active=True
            ),
            'preserves': ProductCategory.objects.create(
                name='Preserves & Jams', 
                slug='preserves-jams', 
                description='Homemade preserves and jams', 
                order=6,
                is_active=True
            ),
            'honey': ProductCategory.objects.create(
                name='Honey & Beeswax', 
                slug='honey-beeswax', 
                description='Local honey and beeswax products', 
                order=7,
                is_active=True
            ),
            'herbs': ProductCategory.objects.create(
                name='Fresh Herbs', 
                slug='fresh-herbs', 
                description='Culinary and medicinal herbs', 
                order=8,
                is_active=True
            ),
            'mushrooms': ProductCategory.objects.create(
                name='Mushrooms', 
                slug='mushrooms', 
                description='Cultivated and wild mushrooms', 
                order=9,
                is_active=True
            ),
            'beverages': ProductCategory.objects.create(
                name='Beverages', 
                slug='beverages', 
                description='Local drinks and refreshments', 
                order=10,
                is_active=True
            ),
        }

        # Current month for determining season status
        current_month = timezone.now().month

        # Helper function to determine if a product is in season based on current month
        def is_in_season(season_start, season_end):
            if not (season_start and season_end):
                return True
            if season_start <= season_end:
                return season_start <= current_month <= season_end
            else:
                return current_month >= season_start or current_month <= season_end

        # Product data with realistic details
        # Note: 'availability' now only uses 'available' or 'unavailable'
        # Seasonality is handled by season_start/season_end and the is_in_season property
        products = [
            # ========== FRUITS ==========
            # Producer 0 - Berry Farm
            {'name': 'Strawberries', 'description': 'Sweet, hand-picked strawberries, perfect for desserts', 'price': 4.50, 'unit': 'kg', 'stock_quantity': 120, 'category': categories['fruits'], 'producer': producers[0], 'is_organic': True, 'season_start': 5, 'season_end': 8, 'availability': 'available', 'harvest_date': date(2026, 2, 15)},
            {'name': 'Raspberries', 'description': 'Fresh raspberries bursting with flavor', 'price': 5.00, 'unit': 'kg', 'stock_quantity': 80, 'category': categories['fruits'], 'producer': producers[0], 'is_organic': True, 'season_start': 6, 'season_end': 9, 'availability': 'available', 'harvest_date': date(2026, 1, 20)},
            {'name': 'Blueberries', 'description': 'Organic wild blueberries, rich in antioxidants', 'price': 6.00, 'unit': 'kg', 'stock_quantity': 50, 'category': categories['fruits'], 'producer': producers[0], 'is_organic': True, 'season_start': 6, 'season_end': 8, 'availability': 'available', 'harvest_date': date(2026, 1, 10)},
            {'name': 'Blackberries', 'description': 'Juicy blackberries from hedgerows', 'price': 4.80, 'unit': 'kg', 'stock_quantity': 60, 'category': categories['fruits'], 'producer': producers[0], 'is_organic': True, 'season_start': 7, 'season_end': 9, 'availability': 'available', 'harvest_date': date(2026, 1, 25)},
            
            # Producer 1 - Orchard Farm
            {'name': 'Apples - Gala', 'description': 'Sweet and crisp Gala apples', 'price': 3.00, 'unit': 'kg', 'stock_quantity': 200, 'category': categories['fruits'], 'producer': producers[1], 'is_organic': False, 'season_start': 8, 'season_end': 11, 'availability': 'available', 'harvest_date': date(2025, 10, 20)},
            {'name': 'Apples - Bramley', 'description': 'Traditional cooking apples', 'price': 2.50, 'unit': 'kg', 'stock_quantity': 150, 'category': categories['fruits'], 'producer': producers[1], 'is_organic': False, 'season_start': 8, 'season_end': 10, 'availability': 'available', 'harvest_date': date(2025, 10, 15)},
            {'name': 'Pears - Conference', 'description': 'Sweet and juicy conference pears', 'price': 3.20, 'unit': 'kg', 'stock_quantity': 120, 'category': categories['fruits'], 'producer': producers[1], 'is_organic': True, 'season_start': 8, 'season_end': 10, 'availability': 'available', 'harvest_date': date(2025, 10, 5)},
            {'name': 'Plums', 'description': 'Sweet Victoria plums', 'price': 4.00, 'unit': 'kg', 'stock_quantity': 90, 'category': categories['fruits'], 'producer': producers[1], 'is_organic': False, 'season_start': 7, 'season_end': 9, 'availability': 'available', 'harvest_date': date(2025, 9, 1)},
            {'name': 'Oranges', 'description': 'Juicy navel oranges', 'price': 3.50, 'unit': 'kg', 'stock_quantity': 0, 'category': categories['fruits'], 'producer': producers[2], 'is_organic': False, 'season_start': 12, 'season_end': 3, 'availability': 'unavailable', 'harvest_date': date(2025, 12, 5)},
            
            # ========== VEGETABLES ==========
            # Producer 1
            {'name': 'Tomatoes - Vine', 'description': 'Vine-ripened tomatoes, full of flavor', 'price': 2.75, 'unit': 'kg', 'stock_quantity': 150, 'category': categories['vegetables'], 'producer': producers[1], 'is_organic': True, 'season_start': 6, 'season_end': 9, 'availability': 'available', 'harvest_date': date(2026, 2, 28)},
            {'name': 'Cherry Tomatoes', 'description': 'Sweet cherry tomatoes, perfect for salads', 'price': 3.50, 'unit': 'kg', 'stock_quantity': 100, 'category': categories['vegetables'], 'producer': producers[1], 'is_organic': True, 'season_start': 6, 'season_end': 9, 'availability': 'available', 'harvest_date': date(2026, 2, 20)},
            {'name': 'Carrots', 'description': 'Fresh organic carrots, sweet and crunchy', 'price': 1.80, 'unit': 'kg', 'stock_quantity': 300, 'category': categories['vegetables'], 'producer': producers[1], 'is_organic': True, 'season_start': 3, 'season_end': 11, 'availability': 'available', 'harvest_date': date(2026, 2, 10)},
            {'name': 'Spinach', 'description': 'Baby spinach leaves, perfect for salads', 'price': 3.25, 'unit': 'kg', 'stock_quantity': 80, 'category': categories['vegetables'], 'producer': producers[1], 'is_organic': False, 'season_start': 3, 'season_end': 5, 'availability': 'available', 'harvest_date': date(2026, 1, 25)},
            {'name': 'Kale', 'description': 'Curly kale, nutrient-rich', 'price': 2.50, 'unit': 'kg', 'stock_quantity': 60, 'category': categories['vegetables'], 'producer': producers[1], 'is_organic': True, 'season_start': 9, 'season_end': 3, 'availability': 'available', 'harvest_date': date(2026, 1, 18)},
            
            # Producer 2 - Root Farm
            {'name': 'Potatoes - Maris Piper', 'description': 'Excellent for roasting and mashing', 'price': 1.50, 'unit': 'kg', 'stock_quantity': 500, 'category': categories['vegetables'], 'producer': producers[2], 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 1, 15)},
            {'name': 'Sweet Potatoes', 'description': 'Orange-fleshed sweet potatoes', 'price': 2.80, 'unit': 'kg', 'stock_quantity': 150, 'category': categories['vegetables'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 1, 20)},
            {'name': 'Onions', 'description': 'Brown onions, perfect for cooking', 'price': 1.20, 'unit': 'kg', 'stock_quantity': 400, 'category': categories['vegetables'], 'producer': producers[2], 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2025, 12, 10)},
            {'name': 'Garlic', 'description': 'Fresh garlic bulbs', 'price': 8.00, 'unit': 'kg', 'stock_quantity': 50, 'category': categories['vegetables'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 1, 5)},
            
            # ========== DAIRY & EGGS ==========
            # Producer 2
            {'name': 'Fresh Milk', 'description': 'Whole milk from grass-fed cows', 'price': 2.50, 'unit': 'litre', 'stock_quantity': 60, 'category': categories['dairy'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 3, 1)},
            {'name': 'Semi-Skimmed Milk', 'description': 'Creamy semi-skimmed milk', 'price': 2.20, 'unit': 'litre', 'stock_quantity': 80, 'category': categories['dairy'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 3, 1)},
            {'name': 'Cheddar Cheese', 'description': 'Aged farmhouse cheddar', 'price': 8.00, 'unit': 'kg', 'stock_quantity': 5, 'category': categories['dairy'], 'producer': producers[2], 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2025, 11, 20)},
            {'name': 'Free Range Eggs', 'description': 'Farm fresh free range eggs', 'price': 4.00, 'unit': 'dozen', 'stock_quantity': 90, 'category': categories['dairy'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 27)},
            {'name': 'Butter', 'description': 'Salted butter from grass-fed cows', 'price': 5.50, 'unit': 'kg', 'stock_quantity': 30, 'category': categories['dairy'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 15)},
            
            # Producer 3 - Dairy Farm
            {'name': 'Greek Yogurt', 'description': 'Thick and creamy Greek yogurt', 'price': 3.80, 'unit': 'kg', 'stock_quantity': 40, 'category': categories['dairy'], 'producer': producers[3], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 28)},
            
            # ========== BAKERY ==========
            # Producer 0 - Bakery
            {'name': 'Sourdough Bread', 'description': 'Handmade sourdough loaf', 'price': 5.50, 'unit': 'each', 'stock_quantity': 25, 'category': categories['bakery'], 'producer': producers[0], 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 3, 2)},
            {'name': 'Wholemeal Loaf', 'description': 'Nutritious wholemeal bread', 'price': 3.80, 'unit': 'each', 'stock_quantity': 35, 'category': categories['bakery'], 'producer': producers[0], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 3, 2)},
            {'name': 'Croissants', 'description': 'Buttery, flaky croissants', 'price': 2.50, 'unit': 'each', 'stock_quantity': 20, 'category': categories['bakery'], 'producer': producers[0], 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 3, 1)},
            {'name': 'Granola', 'description': 'Homemade granola with oats and honey', 'price': 6.00, 'unit': 'kg', 'stock_quantity': 15, 'category': categories['bakery'], 'producer': producers[0], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 20)},
            
            # ========== PRESERVES ==========
            # Producer 1
            {'name': 'Strawberry Jam', 'description': 'Traditional strawberry jam', 'price': 4.50, 'unit': 'jar', 'stock_quantity': 40, 'category': categories['preserves'], 'producer': producers[1], 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2025, 8, 15)},
            {'name': 'Raspberry Jam', 'description': 'Seedless raspberry jam', 'price': 5.00, 'unit': 'jar', 'stock_quantity': 35, 'category': categories['preserves'], 'producer': producers[1], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2025, 9, 10)},
            {'name': 'Marmalade', 'description': 'Seville orange marmalade', 'price': 4.20, 'unit': 'jar', 'stock_quantity': 25, 'category': categories['preserves'], 'producer': producers[1], 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 1, 5)},
            
            # ========== HONEY & BEESWAX ==========
            # Producer 2
            {'name': 'Wildflower Honey', 'description': 'Raw wildflower honey', 'price': 8.00, 'unit': 'jar', 'stock_quantity': 30, 'category': categories['honey'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2025, 9, 1)},
            {'name': 'Manuka Honey', 'description': 'Premium Manuka honey', 'price': 15.00, 'unit': 'jar', 'stock_quantity': 10, 'category': categories['honey'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2025, 8, 20)},
            {'name': 'Beeswax Candles', 'description': 'Pure beeswax candles', 'price': 12.00, 'unit': 'pair', 'stock_quantity': 15, 'category': categories['honey'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2025, 10, 1)},
            
            # ========== HERBS ==========
            # Producer 3
            {'name': 'Basil', 'description': 'Fresh basil leaves', 'price': 2.50, 'unit': 'bunch', 'stock_quantity': 40, 'category': categories['herbs'], 'producer': producers[3], 'is_organic': True, 'season_start': 5, 'season_end': 9, 'availability': 'available', 'harvest_date': date(2026, 2, 25)},
            {'name': 'Rosemary', 'description': 'Fresh rosemary sprigs', 'price': 2.00, 'unit': 'bunch', 'stock_quantity': 50, 'category': categories['herbs'], 'producer': producers[3], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 20)},
            {'name': 'Mint', 'description': 'Fresh mint leaves', 'price': 2.00, 'unit': 'bunch', 'stock_quantity': 45, 'category': categories['herbs'], 'producer': producers[3], 'is_organic': True, 'season_start': 4, 'season_end': 10, 'availability': 'available', 'harvest_date': date(2026, 2, 22)},
            {'name': 'Parsley', 'description': 'Flat-leaf parsley', 'price': 1.80, 'unit': 'bunch', 'stock_quantity': 60, 'category': categories['herbs'], 'producer': producers[3], 'is_organic': True, 'season_start': 3, 'season_end': 11, 'availability': 'available', 'harvest_date': date(2026, 2, 18)},
            
            # ========== MUSHROOMS ==========
            # Producer 0
            {'name': 'Button Mushrooms', 'description': 'Fresh white button mushrooms', 'price': 4.50, 'unit': 'kg', 'stock_quantity': 30, 'category': categories['mushrooms'], 'producer': producers[0], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 28)},
            {'name': 'Oyster Mushrooms', 'description': 'Delicate oyster mushrooms', 'price': 8.00, 'unit': 'kg', 'stock_quantity': 15, 'category': categories['mushrooms'], 'producer': producers[0], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 25)},
            {'name': 'Shiitake Mushrooms', 'description': 'Dried shiitake mushrooms', 'price': 12.00, 'unit': 'kg', 'stock_quantity': 10, 'category': categories['mushrooms'], 'producer': producers[0], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 20)},
            
            # ========== BEVERAGES ==========
            # Producer 1
            {'name': 'Apple Juice', 'description': 'Cold-pressed apple juice', 'price': 4.00, 'unit': 'litre', 'stock_quantity': 50, 'category': categories['beverages'], 'producer': producers[1], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2025, 10, 10)},
            {'name': 'Elderflower Cordial', 'description': 'Refreshing elderflower cordial', 'price': 6.00, 'unit': 'bottle', 'stock_quantity': 25, 'category': categories['beverages'], 'producer': producers[1], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2025, 6, 15)},
            
            # ========== MEAT ==========
            # Producer 2
            {'name': 'Chicken Breast', 'description': 'Free range chicken breast fillets', 'price': 9.50, 'unit': 'kg', 'stock_quantity': 40, 'category': categories['meat'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 25)},
            {'name': 'Chicken Thighs', 'description': 'Free range chicken thighs', 'price': 8.00, 'unit': 'kg', 'stock_quantity': 35, 'category': categories['meat'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 24)},
            {'name': 'Minced Beef', 'description': 'Grass-fed minced beef', 'price': 8.50, 'unit': 'kg', 'stock_quantity': 30, 'category': categories['meat'], 'producer': producers[2], 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 20)},
            {'name': 'Lamb Chops', 'description': 'Locally sourced lamb chops', 'price': 14.00, 'unit': 'kg', 'stock_quantity': 0, 'category': categories['meat'], 'producer': producers[3], 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'unavailable', 'harvest_date': date(2025, 12, 18)},
            {'name': 'Pork Sausages', 'description': 'Traditional pork sausages', 'price': 7.50, 'unit': 'kg', 'stock_quantity': 25, 'category': categories['meat'], 'producer': producers[3], 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 10)},
        ]

        # Create products
        created_count = 0
        for product_data in products:
            try:
                product = Product.objects.create(**product_data)
                created_count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Failed to create {product_data["name"]}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Successfully created {len(categories)} categories and {created_count} products'))
        
        # Print season status for current month
        self.stdout.write(f"\nCurrent month: {timezone.now().strftime('%B')}")
        in_season_count = sum(1 for p in Product.objects.all() if p.is_in_season)
        self.stdout.write(f"Products in season: {in_season_count}/{created_count}")