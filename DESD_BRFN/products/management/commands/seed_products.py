from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date
from products.models import Product, ProductCategory
from mainApp.models import ProducerProfile


class Command(BaseCommand):
    help = 'Seed products with mock data'

    def handle(self, *args, **options):
        if Product.objects.exists():
            self.stdout.write('Products already seeded, skipping.')
            return

        # Get existing producers
        producers = list(ProducerProfile.objects.all()[:3])
        if len(producers) < 3:
            self.stdout.write(self.style.ERROR(f'Need 3 producers, found {len(producers)}. Create more producers first.'))
            return

        p1, p2, p3 = producers

        # Create categories
        categories = {
            'fruits': ProductCategory.objects.create(name='Fruits', slug='fruits', description='Fresh fruits', order=1),
            'vegetables': ProductCategory.objects.create(name='Vegetables', slug='vegetables', description='Fresh vegetables', order=2),
            'dairy': ProductCategory.objects.create(name='Dairy', slug='dairy', description='Dairy products', order=3),
            'grains': ProductCategory.objects.create(name='Grains', slug='grains', description='Grains and cereals', order=4),
            'meat': ProductCategory.objects.create(name='Meat', slug='meat', description='Fresh meat', order=5),
        }

        products = [
            # Fruits — Producer 1
            {'name': 'Strawberries', 'description': 'Sweet, hand-picked strawberries', 'price': 4.50, 'unit': 'kg', 'stock_quantity': 120, 'category': categories['fruits'], 'producer': p1, 'is_organic': True, 'season_start': 5, 'season_end': 8, 'availability': 'in_season', 'harvest_date': date(2026, 2, 15)},
            {'name': 'Apples', 'description': 'Crisp red apples from local orchards', 'price': 3.00, 'unit': 'kg', 'stock_quantity': 200, 'category': categories['fruits'], 'producer': p1, 'is_organic': False, 'season_start': 8, 'season_end': 11, 'availability': 'available', 'harvest_date': date(2025, 10, 20)},
            {'name': 'Blueberries', 'description': 'Organic wild blueberries', 'price': 6.00, 'unit': 'kg', 'stock_quantity': 50, 'category': categories['fruits'], 'producer': p1, 'is_organic': True, 'season_start': 6, 'season_end': 8, 'availability': 'in_season', 'harvest_date': date(2026, 1, 10)},
            {'name': 'Oranges', 'description': 'Juicy navel oranges', 'price': 3.50, 'unit': 'kg', 'stock_quantity': 0, 'category': categories['fruits'], 'producer': p2, 'is_organic': False, 'season_start': 12, 'season_end': 3, 'availability': 'out_of_season', 'harvest_date': date(2025, 12, 5)},

            # Vegetables — Producer 2
            {'name': 'Tomatoes', 'description': 'Vine-ripened tomatoes', 'price': 2.75, 'unit': 'kg', 'stock_quantity': 150, 'category': categories['vegetables'], 'producer': p2, 'is_organic': True, 'season_start': 6, 'season_end': 9, 'availability': 'in_season', 'harvest_date': date(2026, 2, 28)},
            {'name': 'Carrots', 'description': 'Fresh organic carrots', 'price': 1.80, 'unit': 'kg', 'stock_quantity': 300, 'category': categories['vegetables'], 'producer': p2, 'is_organic': True, 'season_start': 3, 'season_end': 11, 'availability': 'available', 'harvest_date': date(2026, 2, 10)},
            {'name': 'Spinach', 'description': 'Baby spinach leaves', 'price': 3.25, 'unit': 'kg', 'stock_quantity': 80, 'category': categories['vegetables'], 'producer': p2, 'is_organic': False, 'season_start': 3, 'season_end': 5, 'availability': 'available', 'harvest_date': date(2026, 1, 25)},
            {'name': 'Potatoes', 'description': 'Russet potatoes', 'price': 1.50, 'unit': 'kg', 'stock_quantity': 500, 'category': categories['vegetables'], 'producer': p3, 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 1, 15)},

            # Dairy — Producer 3
            {'name': 'Fresh Milk', 'description': 'Whole milk from grass-fed cows', 'price': 2.50, 'unit': 'litre', 'stock_quantity': 60, 'category': categories['dairy'], 'producer': p3, 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 3, 1)},
            {'name': 'Cheddar Cheese', 'description': 'Aged farmhouse cheddar', 'price': 8.00, 'unit': 'kg', 'stock_quantity': 5, 'category': categories['dairy'], 'producer': p3, 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2025, 11, 20)},
            {'name': 'Free Range Eggs', 'description': 'Farm fresh free range eggs', 'price': 4.00, 'unit': 'dozen', 'stock_quantity': 90, 'category': categories['dairy'], 'producer': p3, 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 27)},

            # Grains — Producer 1
            {'name': 'Sourdough Bread', 'description': 'Handmade sourdough loaf', 'price': 5.50, 'unit': 'each', 'stock_quantity': 25, 'category': categories['grains'], 'producer': p1, 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 3, 2)},
            {'name': 'Oats', 'description': 'Rolled oats for porridge', 'price': 2.00, 'unit': 'kg', 'stock_quantity': 200, 'category': categories['grains'], 'producer': p1, 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2025, 9, 15)},

            # Meat — Producer 2
            {'name': 'Chicken Breast', 'description': 'Free range chicken breast fillets', 'price': 9.50, 'unit': 'kg', 'stock_quantity': 40, 'category': categories['meat'], 'producer': p2, 'is_organic': True, 'season_start': None, 'season_end': None, 'availability': 'available', 'harvest_date': date(2026, 2, 25)},
            {'name': 'Lamb Chops', 'description': 'Locally sourced lamb chops', 'price': 14.00, 'unit': 'kg', 'stock_quantity': 0, 'category': categories['meat'], 'producer': p3, 'is_organic': False, 'season_start': None, 'season_end': None, 'availability': 'unavailable', 'harvest_date': date(2025, 12, 18)},
        ]

        for p in products:
            Product.objects.create(**p)

        self.stdout.write(self.style.SUCCESS(f'Created {len(categories)} categories and {len(products)} products'))