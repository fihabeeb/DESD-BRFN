# producers/management/commands/seed_producers.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from mainApp.models import ProducerProfile, Address
import random
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed producer table with mock data and addresses'

    def handle(self, *args, **options):
        # Sample data lists
        first_names = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emma', 'Robert', 'Lisa', 
                      'William', 'Anna', 'James', 'Maria', 'Thomas', 'Susan', 'Paul', 'Karen']
        
        last_names = ['Smith', 'Jones', 'Williams', 'Brown', 'Taylor', 'Davies', 'Evans', 'Wilson',
                     'Thomas', 'Johnson', 'Roberts', 'Walker', 'Wright', 'Robinson', 'Thompson', 'White']
        
        farm_names = [
            'Green Acres Farm', 'Sunny Meadow Organic', 'Valley View Produce', 'Oak Tree Orchard', 
            'River Bend Dairy', 'Happy Hens Free Range', 'Organic Oasis', 'Heritage Harvest', 
            'Wildflower Farm', 'Pasture Prime Meats', 'Golden Grain Bakery', 'Blue Sky Farm',
            'Red Barn Produce', 'Misty Morning Mushrooms', 'Country Gardens', 'Bristol Valley Farm',
            'Hillside Dairy', 'Clifton Orchard', 'St. George\'s Market Garden', 'Bedminster Bees'
        ]
        
        # Real Bristol area addresses with coordinates
        farm_addresses = [
            {'line1': 'Long Ashton Farm', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS41 9AA', 'lat': 51.4345, 'lon': -2.6560},
            {'line1': 'Wrington Farm', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS40 5NB', 'lat': 51.3675, 'lon': -2.7630},
            {'line1': 'Chew Valley Farm', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS40 8XB', 'lat': 51.3470, 'lon': -2.6170},
            {'line1': 'Keynsham Farm', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS31 1AB', 'lat': 51.4130, 'lon': -2.4960},
            {'line1': 'Portishead Farm', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS20 7AB', 'lat': 51.4840, 'lon': -2.7660},
            {'line1': 'Bath Road Farm', 'city': 'Bath', 'county': 'Somerset', 'postcode': 'BA1 2AB', 'lat': 51.3820, 'lon': -2.3590},
            {'line1': 'Mendip Hills Farm', 'city': 'Wells', 'county': 'Somerset', 'postcode': 'BA5 3AB', 'lat': 51.2080, 'lon': -2.6520},
            {'line1': 'Yate Farm', 'city': 'Bristol', 'county': 'Gloucestershire', 'postcode': 'BS37 4AB', 'lat': 51.5400, 'lon': -2.4070},
            {'line1': 'Thornbury Farm', 'city': 'Bristol', 'county': 'Gloucestershire', 'postcode': 'BS35 2AB', 'lat': 51.6070, 'lon': -2.5260},
            {'line1': 'Clevedon Farm', 'city': 'Clevedon', 'county': 'Somerset', 'postcode': 'BS21 6AB', 'lat': 51.4350, 'lon': -2.8530},
        ]
        
        phone_prefixes = ['07700', '07701', '07702', '07703', '07704', '07705']
        
        self.stdout.write(self.style.SUCCESS('Creating mock producers...'))
        
        created_count = 0
        
        for i in range(10):  # Create 10 producers
            username = f"demo_producer{i+1}"
            email = f"demo_producer{i+1}@example.com"
            
            # Skip if already exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(f"Skipping {username} - already exists"))
                continue
            
            # Get random address data
            addr_data = random.choice(farm_addresses)
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password='123',
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                role=User.Role.PRODUCER,
                phone_number=f"{random.choice(phone_prefixes)} {random.randint(100, 999)} {random.randint(100, 999)}",
            )
            
            profile = user.producer_profile  # This will exist due to the signal
            profile.business_name = random.choice(farm_names)
            profile.save()

            
            # Create farm address
            address = Address.objects.create(
                user=user,
                address_line1=addr_data['line1'],
                address_line2=f"Farm {random.randint(1, 10)}" if random.choice([True, False]) else '',
                city=addr_data['city'],
                county=addr_data['county'],
                post_code=addr_data['postcode'],
                country='UK',
                address_type='farm',
                is_default=True,
                latitude=Decimal(str(addr_data['lat'])),
                longitude=Decimal(str(addr_data['lon'])),
            )
            
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"  Created producer: {user.username} - {profile.business_name} at {addr_data['postcode']}"))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} producers!'))