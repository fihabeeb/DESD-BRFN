# products/management/commands/seed_products_enhanced.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from products.models import Product, ProductCategory
from mainApp.models import ProducerProfile
import random


class Command(BaseCommand):
    help = 'Seed enhanced products with more variety for LSTM training'

    def handle(self, *args, **options):
        if Product.objects.count() > 100:
            self.stdout.write(f'Already have {Product.objects.count()} products, skipping.')
            return

        # Get existing producers
        producers = list(ProducerProfile.objects.all())
        if len(producers) < 4:
            self.stdout.write(self.style.ERROR(f'Need at least 4 producers, found {len(producers)}. Create more producers first.'))
            return

        # Create or get categories
        categories = self.get_or_create_categories()
        
        # Generate enhanced product list
        products = self.generate_enhanced_products(categories, producers)
        
        # Create products
        created_count = 0
        for product_data in products:
            try:
                # Check if product already exists
                if not Product.objects.filter(name=product_data['name'], producer=product_data['producer']).exists():
                    Product.objects.create(**product_data)
                    created_count += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Failed to create {product_data["name"]}: {e}'))

        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} products (Total: {Product.objects.count()})'))

    def get_or_create_categories(self):
        """Get or create product categories with subcategories"""
        categories = {}
        
        main_categories = {
            'fruits': ['Berries', 'Tree Fruits', 'Citrus', 'Tropical', 'Stone Fruits'],
            'vegetables': ['Leafy Greens', 'Root Vegetables', 'Cruciferous', 'Squash', 'Alliums', 'Legumes'],
            'dairy': ['Milk', 'Cheese', 'Yogurt', 'Eggs', 'Butter & Cream'],
            'meat': ['Poultry', 'Beef', 'Goat', 'Lamb', 'Game'],
            'preserves': ['Jams', 'Pickles', 'Chutneys', 'Fermented Foods'],
            'Herbs Spices': ['Fresh Herbs', 'Dried Herbs', 'Spices', 'Teas'],
            'mushrooms': ['Fresh Mushrooms', 'Dried Mushrooms', 'Mushroom Products'],
            'beverages': ['Juices', 'Cordials', 'Fermented Drinks', 'Infusions'],
            'snacks': ['Nuts', 'Dried Fruits', 'Seeds', 'Healthy Snacks'],
            'grains': ['Flour', 'Oats', 'Rice Alternatives', 'Pasta'],
            'Honey Bee': ['Honey', 'Beeswax Products', 'Propolis'],
        }
        
        for main_cat, subcats in main_categories.items():
            main_category, _ = ProductCategory.objects.get_or_create(
                name=main_cat.title(),
                defaults={
                    'slug': main_cat.lower(),
                    'description': f'Fresh {main_cat.lower()} from local producers',
                    'is_active': True
                }
            )
            categories[main_cat] = main_category
        
        return categories

    def generate_enhanced_products(self, categories, producers):
        """Generate 250+ products with realistic variations"""
        products = []
        
        # Helper to create product variations
        def add_product(name, category, producer, price, unit, is_organic=True, season_start=None, season_end=None, stock=100):
            products.append({
                'name': name,
                'description': f'Fresh {name.lower()} from local farm',
                'price': price,
                'unit': unit,
                'stock_quantity': stock,
                'category': categories[category],
                'producer': producer,
                'is_organic': is_organic,
                'season_start': season_start,
                'season_end': season_end,
                'availability': 'available',
                'harvest_date': timezone.now().date() - timedelta(days=random.randint(1, 30))
            })
        
        # 1. FRUITS - 50 products
        self.stdout.write("Creating fruits...")
        fruit_varieties = {
            'Berries': [('Strawberries', 4.5), ('Raspberries', 5.0), ('Blueberries', 6.0), ('Blackberries', 4.8), 
                       ('Gooseberries', 5.5), ('Red Currants', 5.2), ('Black Currants', 5.2), ('Elderberries', 6.0),
                       ('Cranberries', 4.5), ('Bilberries', 7.0)],
            'Tree Fruits': [('Gala Apples', 3.0), ('Bramley Apples', 2.5), ('Conference Pears', 3.2), ('Comice Pears', 3.5),
                          ('Victoria Plums', 4.0), ('Greengage Plums', 4.5), ('Cherries', 8.0), ('Peaches', 5.0),
                          ('Nectarines', 5.5), ('Apricots', 6.0)],
            'Citrus': [('Navel Oranges', 3.5), ('Blood Oranges', 4.0), ('Lemons', 2.5), ('Limes', 3.0),
                      ('Grapefruit', 3.0), ('Mandarins', 4.0), ('Clementines', 4.5), ('Kumquats', 6.0)],
            'Tropical': [('Bananas', 2.0), ('Mangoes', 4.0), ('Pineapples', 3.5), ('Papaya', 5.0),
                        ('Kiwi', 3.5), ('Passion Fruit', 6.0), ('Lychee', 8.0), ('Dragon Fruit', 7.0)],
            'Stone Fruits': [('Apricots', 6.0), ('Plums', 4.0), ('Damsons', 4.5), ('Mulberries', 7.0)]
        }
        
        for category, varieties in fruit_varieties.items():
            for name, price in varieties:
                producer_idx = random.randint(0, len(producers)-1)
                add_product(name, 'fruits', producers[producer_idx], price, 'kg', 
                          is_organic=random.choice([True, False]),
                          season_start=random.choice([5,6,7,8]), 
                          season_end=random.choice([8,9,10,11]))
        
        # 2. VEGETABLES - 50 products
        self.stdout.write("Creating vegetables...")
        veg_varieties = {
            'Leafy Greens': [('Spinach', 3.25), ('Kale', 2.5), ('Lettuce', 1.8), ('Swiss Chard', 3.0),
                           ('Arugula', 4.0), ('Watercress', 3.5), ('Collard Greens', 2.8), ('Bok Choy', 3.0),
                           ('Spring Mix', 4.5), ('Romaine Lettuce', 2.0)],
            'Root Vegetables': [('Carrots', 1.8), ('Potatoes', 1.5), ('Sweet Potatoes', 2.8), ('Parsnips', 2.2),
                              ('Beets', 2.0), ('Turnips', 1.8), ('Radishes', 2.0), ('Jerusalem Artichokes', 4.0),
                              ('Celery Root', 3.0), ('Horseradish', 5.0)],
            'Cruciferous': [('Broccoli', 2.5), ('Cauliflower', 2.5), ('Brussels Sprouts', 3.0), ('Cabbage', 1.2),
                           ('Romanesco', 4.0), ('Kohlrabi', 2.5), ('Broccolini', 3.5), ('Chinese Cabbage', 2.0)],
            'Squash': [('Butternut Squash', 2.5), ('Acorn Squash', 2.5), ('Pumpkin', 1.8), ('Zucchini', 2.0),
                      ('Yellow Squash', 2.0), ('Spaghetti Squash', 2.8), ('Delicata Squash', 3.0), ('Kabocha Squash', 3.5)],
            'Alliums': [('Onions', 1.2), ('Garlic', 8.0), ('Leeks', 2.5), ('Shallots', 4.0),
                       ('Spring Onions', 1.5), ('Red Onions', 1.5), ('Ramps', 12.0), ('Scallions', 1.5)],
            'Legumes': [('Green Beans', 3.0), ('Snow Peas', 4.0), ('Sugar Snap Peas', 4.0), ('Broad Beans', 3.5),
                       ('Peas', 2.5), ('Edamame', 5.0), ('Fava Beans', 4.0), ('Lima Beans', 3.5)]
        }
        
        for category, varieties in veg_varieties.items():
            for name, price in varieties:
                producer_idx = random.randint(0, len(producers)-1)
                add_product(name, 'vegetables', producers[producer_idx], price, 'kg', 
                          is_organic=random.choice([True, False]))
        
        # 3. DAIRY - 35 products
        self.stdout.write("Creating dairy products...")
        dairy_products = [
            ('Whole Milk', 2.5, 'litre'), ('Semi-Skimmed Milk', 2.2, 'litre'), ('Skimmed Milk', 2.0, 'litre'),
            ('Gold Top Milk', 3.5, 'litre'), ('Goat Milk', 4.0, 'litre'), ('Sheep Milk', 5.0, 'litre'),
            ('Cheddar Cheese', 8.0, 'kg'), ('Red Leicester', 7.5, 'kg'), ('Double Gloucester', 7.5, 'kg'),
            ('Stilton', 12.0, 'kg'), ('Brie', 9.0, 'kg'), ('Camembert', 9.0, 'kg'), ('Goat Cheese', 10.0, 'kg'),
            ('Feta', 8.0, 'kg'), ('Mozzarella', 6.0, 'kg'), ('Parmesan', 15.0, 'kg'), ('Blue Cheese', 11.0, 'kg'),
            ('Halloumi', 10.0, 'kg'), ('Ricotta', 7.0, 'kg'), ('Cottage Cheese', 5.0, 'kg'),
            ('Free Range Eggs', 4.0, 'dozen'), ('Duck Eggs', 6.0, 'half dozen'), ('Quail Eggs', 5.0, 'dozen'),
            ('Greek Yogurt', 3.8, 'kg'), ('Natural Yogurt', 3.0, 'kg'), ('Skyr', 4.0, 'kg'), ('Probiotic Yogurt', 4.5, 'kg'),
            ('Butter', 5.5, 'kg'), ('Clotted Cream', 4.5, 'jar'), ('Double Cream', 3.5, 'litre'),
            ('Soured Cream', 3.0, 'litre'), ('Creme Fraiche', 4.0, 'litre'), ('Buttermilk', 2.5, 'litre'),
            ('Ghee', 8.0, 'jar'), ('Lactose Free Milk', 3.0, 'litre')
        ]
        
        for name, price, unit in dairy_products:
            producer_idx = random.randint(0, len(producers)-1)
            add_product(name, 'dairy', producers[producer_idx], price, unit, is_organic=random.choice([True, False]))
        
        # 4. MEAT - 35 products
        self.stdout.write("Creating meat products...")
        meat_products = [
            # Poultry
            ('Chicken Breast', 9.5, 'kg'), ('Chicken Thighs', 8.0, 'kg'), ('Whole Chicken', 7.0, 'kg'),
            ('Chicken Wings', 6.0, 'kg'), ('Chicken Drumsticks', 6.5, 'kg'), ('Turkey Breast', 12.0, 'kg'),
            ('Duck Breast', 15.0, 'kg'), ('Goose', 18.0, 'each'), ('Quail', 8.0, 'each'), ('Cornish Hen', 6.0, 'each'),
            # Beef
            ('Minced Beef', 8.5, 'kg'), ('Beef Steak', 18.0, 'kg'), ('Beef Roast', 15.0, 'kg'),
            ('Beef Brisket', 12.0, 'kg'), ('Beef Fillet', 25.0, 'kg'), ('Ribeye Steak', 22.0, 'kg'),
            ('Sirloin Steak', 20.0, 'kg'), ('Beef Short Ribs', 14.0, 'kg'),
            # Goat
            ('Goat Chops', 8.0, 'kg'), ('Goat Shoulder', 9.0, 'kg'), ('Goat Sausages', 7.5, 'kg'),
            ('Goat Mince', 10.0, 'kg'), ('Goat Leg', 12.0, 'kg'), ('Goat Loin', 9.0, 'kg'),
            ('Goat Ribs', 8.0, 'kg'), ('Goat Fillet', 14.0, 'kg'),
            # Lamb
            ('Lamb Chops', 14.0, 'kg'), ('Lamb Shoulder', 12.0, 'kg'), ('Lamb Leg', 13.0, 'kg'),
            ('Lamb Rack', 20.0, 'kg'), ('Minced Lamb', 10.0, 'kg'),
            # Game
            ('Venison', 20.0, 'kg'), ('Rabbit', 12.0, 'each'), ('Pheasant', 15.0, 'each'), ('Partridge', 12.0, 'each')
        ]
        
        for name, price, unit in meat_products:
            producer_idx = random.randint(0, len(producers)-1)
            add_product(name, 'meat', producers[producer_idx], price, unit, is_organic=random.choice([True, False]))
        
        # 6. HERBS & SPICES - 25 products
        self.stdout.write("Creating herbs and spices...")
        herb_products = [
            # Fresh Herbs
            ('Basil', 2.5, 'bunch'), ('Rosemary', 2.0, 'bunch'), ('Thyme', 2.0, 'bunch'),
            ('Mint', 2.0, 'bunch'), ('Parsley', 1.8, 'bunch'), ('Coriander', 2.0, 'bunch'),
            ('Dill', 2.5, 'bunch'), ('Oregano', 2.0, 'bunch'), ('Sage', 2.0, 'bunch'),
            ('Chives', 2.0, 'bunch'), ('Tarragon', 2.5, 'bunch'), ('Marjoram', 2.5, 'bunch'),
            ('Chervil', 3.0, 'bunch'), ('Lemon Balm', 2.5, 'bunch'),
            # Dried Herbs
            ('Bay Leaves', 1.5, 'pack'), ('Dried Oregano', 3.0, 'jar'), ('Dried Thyme', 3.0, 'jar'),
            ('Dried Rosemary', 3.0, 'jar'), ('Dried Sage', 3.0, 'jar'),
            # Spices
            ('Paprika', 4.0, 'jar'), ('Cumin', 4.0, 'jar'), ('Turmeric', 4.0, 'jar'),
            ('Cinnamon', 5.0, 'jar'), ('Nutmeg', 5.0, 'jar'), ('Cloves', 6.0, 'jar'),
            ('Cardamom', 8.0, 'jar'), ('Coriander Seeds', 4.0, 'jar'), ('Fennel Seeds', 4.0, 'jar'),
            ('Star Anise', 7.0, 'jar'), ('Saffron', 15.0, 'jar'), ('Vanilla Pods', 12.0, 'pack')
        ]
        
        for name, price, unit in herb_products:
            producer_idx = random.randint(0, len(producers)-1)
            add_product(name, 'Herbs Spices', producers[producer_idx], price, unit, is_organic=random.choice([True, False]))
        
        # 7. MUSHROOMS - 20 products
        self.stdout.write("Creating mushrooms...")
        mushroom_products = [
            # Fresh Mushrooms
            ('Button Mushrooms', 4.5, 'kg'), ('Chestnut Mushrooms', 5.0, 'kg'), ('Portobello Mushrooms', 6.0, 'kg'),
            ('Oyster Mushrooms', 8.0, 'kg'), ('Shiitake Mushrooms', 12.0, 'kg'), ('Enoki Mushrooms', 10.0, 'kg'),
            ('King Oyster Mushrooms', 9.0, 'kg'), ('Lion\'s Mane', 15.0, 'kg'), ('Maitake', 14.0, 'kg'),
            ('Chanterelle', 20.0, 'kg'), ('Morel', 25.0, 'kg'), ('Porcini', 22.0, 'kg'),
            # Dried Mushrooms
            ('Dried Shiitake', 15.0, 'kg'), ('Dried Porcini', 28.0, 'kg'), ('Dried Morel', 35.0, 'kg'),
            ('Dried Chanterelle', 25.0, 'kg'), ('Mushroom Powder', 12.0, 'jar'),
            # Mushroom Products
            ('Mushroom Pâté', 6.0, 'jar'), ('Pickled Mushrooms', 5.0, 'jar'), ('Mushroom Broth', 4.0, 'litre')
        ]
        
        for name, price, unit in mushroom_products:
            producer_idx = random.randint(0, len(producers)-1)
            add_product(name, 'mushrooms', producers[producer_idx], price, unit, is_organic=random.choice([True, False]))
        
        # 8. BEVERAGES - 25 products
        self.stdout.write("Creating beverages...")
        beverage_products = [
            # Juices
            ('Apple Juice', 4.0, 'litre'), ('Orange Juice', 4.5, 'litre'), ('Carrot Juice', 5.0, 'litre'),
            ('Green Juice', 6.0, 'litre'), ('Beetroot Juice', 5.5, 'litre'), ('Cranberry Juice', 5.0, 'litre'),
            ('Pomegranate Juice', 7.0, 'litre'), ('Grape Juice', 4.5, 'litre'),
            # Cordials & Syrups
            ('Elderflower Cordial', 6.0, 'bottle'), ('Ginger Cordial', 6.0, 'bottle'), ('Mint Cordial', 6.0, 'bottle'),
            ('Lemon Syrup', 5.0, 'bottle'), ('Rose Syrup', 7.0, 'bottle'),
            # Fermented Drinks
            ('Kombucha', 5.0, 'litre'), ('Kefir', 6.0, 'litre'), ('Water Kefir', 5.0, 'litre'),
            ('Jun Kombucha', 6.0, 'litre'),
            # Teas & Infusions
            ('Peppermint Tea', 4.0, 'pack'), ('Chamomile Tea', 4.0, 'pack'), ('Elderberry Tea', 5.0, 'pack'),
            ('Rosehip Tea', 4.5, 'pack'), ('Lemon Balm Tea', 4.5, 'pack'), ('Nettle Tea', 4.0, 'pack'),
            ('Rooibos Tea', 5.0, 'pack'), ('Matcha Powder', 12.0, 'jar')
        ]
        
        for name, price, unit in beverage_products:
            producer_idx = random.randint(0, len(producers)-1)
            add_product(name, 'beverages', producers[producer_idx], price, unit, is_organic=random.choice([True, False]))
        
        # 9. SNACKS - 25 products
        self.stdout.write("Creating snacks...")
        snack_products = [
            # Nuts
            ('Walnuts', 12.0, 'kg'), ('Almonds', 14.0, 'kg'), ('Cashews', 16.0, 'kg'), ('Pecans', 15.0, 'kg'),
            ('Hazelnuts', 13.0, 'kg'), ('Brazil Nuts', 14.0, 'kg'), ('Pistachios', 18.0, 'kg'), ('Mixed Nuts', 15.0, 'kg'),
            # Dried Fruits
            ('Dried Apricots', 10.0, 'kg'), ('Dried Dates', 8.0, 'kg'), ('Dried Figs', 12.0, 'kg'),
            ('Raisins', 6.0, 'kg'), ('Dried Cranberries', 9.0, 'kg'), ('Dried Mango', 11.0, 'kg'),
            ('Dried Apple Rings', 8.0, 'kg'), ('Dried Banana Chips', 7.0, 'kg'),
            # Seeds
            ('Pumpkin Seeds', 8.0, 'kg'), ('Sunflower Seeds', 6.0, 'kg'), ('Chia Seeds', 10.0, 'kg'),
            ('Flax Seeds', 5.0, 'kg'), ('Hemp Seeds', 12.0, 'kg'), ('Sesame Seeds', 7.0, 'kg'),
            # Healthy Snacks
            ('Energy Balls', 8.0, 'pack'), ('Granola Bars', 5.0, 'pack'), ('Rice Cakes', 3.0, 'pack'),
            ('Seaweed Snacks', 4.0, 'pack'), ('Roasted Chickpeas', 6.0, 'pack')
        ]
        
        for name, price, unit in snack_products:
            producer_idx = random.randint(0, len(producers)-1)
            add_product(name, 'snacks', producers[producer_idx], price, unit, is_organic=random.choice([True, False]))
        
        # 10. GRAINS - 20 products
        self.stdout.write("Creating grains...")
        grain_products = [
            # Flours
            ('Plain Flour', 2.0, 'kg'), ('Wholemeal Flour', 2.5, 'kg'), ('Strong White Flour', 2.5, 'kg'),
            ('Rye Flour', 3.0, 'kg'), ('Spelt Flour', 4.0, 'kg'), ('Buckwheat Flour', 4.5, 'kg'),
            ('Almond Flour', 12.0, 'kg'), ('Coconut Flour', 8.0, 'kg'),
            # Oats & Grains
            ('Rolled Oats', 2.5, 'kg'), ('Steel Cut Oats', 3.0, 'kg'), ('Porridge Oats', 2.5, 'kg'),
            ('Quinoa', 6.0, 'kg'), ('Buckwheat', 5.0, 'kg'), ('Millet', 4.0, 'kg'),
            # Rice Alternatives
            ('Brown Rice', 3.0, 'kg'), ('Basmati Rice', 4.0, 'kg'), ('Wild Rice', 8.0, 'kg'),
            ('Cauliflower Rice', 5.0, 'kg'), ('Couscous', 3.0, 'kg'), ('Bulgur Wheat', 3.0, 'kg'),
            # Pasta
            ('Spaghetti', 2.5, 'kg'), ('Penne', 2.5, 'kg'), ('Fusilli', 2.5, 'kg'), ('Lasagne Sheets', 3.0, 'kg'),
            ('Gluten Free Pasta', 5.0, 'kg'), ('Fresh Pasta', 6.0, 'kg')
        ]
        
        for name, price, unit in grain_products:
            producer_idx = random.randint(0, len(producers)-1)
            add_product(name, 'grains', producers[producer_idx], price, unit, is_organic=random.choice([True, False]))
        
        # 11. PRESERVES - 20 products
        self.stdout.write("Creating preserves...")
        preserve_products = [
            # Jams
            ('Strawberry Jam', 4.5, 'jar'), ('Raspberry Jam', 5.0, 'jar'), ('Blackberry Jam', 5.0, 'jar'),
            ('Apricot Jam', 5.0, 'jar'), ('Plum Jam', 4.5, 'jar'), ('Marmalade', 4.2, 'jar'),
            ('Blueberry Jam', 5.5, 'jar'), ('Fig Jam', 6.0, 'jar'), ('Cherry Jam', 5.5, 'jar'),
            ('Mixed Berry Jam', 5.0, 'jar'),
            # Pickles
            ('Bread & Butter Pickles', 4.0, 'jar'), ('Dill Pickles', 4.0, 'jar'), ('Pickled Onions', 3.5, 'jar'),
            ('Pickled Beets', 4.0, 'jar'), ('Pickled Eggs', 5.0, 'jar'),
            # Chutneys
            ('Mango Chutney', 5.0, 'jar'), ('Apple Chutney', 4.5, 'jar'), ('Tomato Chutney', 4.5, 'jar'),
            ('Onion Marmalade', 5.0, 'jar'),
            # Fermented
            ('Sauerkraut', 4.0, 'jar'), ('Kimchi', 5.0, 'jar'), ('Kombucha Starter', 8.0, 'bottle')
        ]
        
        for name, price, unit in preserve_products:
            producer_idx = random.randint(0, len(producers)-1)
            add_product(name, 'preserves', producers[producer_idx], price, unit, is_organic=random.choice([True, False]))
        
        # 12. HONEY & BEE PRODUCTS - 15 products
        self.stdout.write("Creating honey and bee products...")
        honey_products = [
            # Honey varieties
            ('Wildflower Honey', 8.0, 'jar'), ('Manuka Honey', 15.0, 'jar'), ('Clover Honey', 7.0, 'jar'),
            ('Orange Blossom Honey', 9.0, 'jar'), ('Lavender Honey', 10.0, 'jar'), ('Acacia Honey', 9.0, 'jar'),
            ('Chestnut Honey', 11.0, 'jar'), ('Heather Honey', 12.0, 'jar'), ('Raw Honeycomb', 10.0, 'piece'),
            ('Honey with Propolis', 12.0, 'jar'),
            # Beeswax products
            ('Beeswax Candles', 12.0, 'pair'), ('Beeswax Wraps', 15.0, 'pack'), ('Beeswax Lip Balm', 5.0, 'each'),
            ('Beeswax Furniture Polish', 8.0, 'jar'),
            # Propolis
            ('Propolis Tincture', 12.0, 'bottle'), ('Propolis Spray', 10.0, 'bottle')
        ]
        
        for name, price, unit in honey_products:
            producer_idx = random.randint(0, len(producers)-1)
            add_product(name, 'Honey Bee', producers[producer_idx], price, unit, is_organic=random.choice([True, False]))
        
        self.stdout.write(f"Total products generated: {len(products)}")
        return products