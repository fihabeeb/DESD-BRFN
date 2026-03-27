# customers/management/commands/seed_customers.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from mainApp.models import CustomerProfile, Address
from customers.models import Cart
import random
from decimal import Decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed customer table with mock data and addresses'

    def handle(self, *args, **options):
        # Sample data lists
        first_names = ['Alice', 'Bob', 'Charlie', 'Diana', 'Edward', 'Fiona', 'George', 'Hannah',
                       'Ian', 'Julia', 'Kevin', 'Laura', 'Matthew', 'Nina', 'Oliver', 'Patricia',
                       'Quentin', 'Rachel', 'Samuel', 'Tina', 'Ulysses', 'Victoria', 'William', 'Xena']
        
        last_names = ['Adams', 'Baker', 'Clark', 'Davis', 'Evans', 'Franklin', 'Garcia', 'Harris',
                     'Irving', 'Johnson', 'King', 'Lewis', 'Miller', 'Nelson', 'Oscar', 'Parker',
                     'Quinn', 'Roberts', 'Smith', 'Taylor', 'Upton', 'Vaughn', 'Wilson', 'Young']
        
        # Real Bristol area customer addresses
        customer_addresses = [
            {'line1': '1 Park Street', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS1 5JG', 'lat': 51.4545, 'lon': -2.5940},
            {'line1': '2 Queen Square', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS1 4LH', 'lat': 51.4505, 'lon': -2.5960},
            {'line1': '15 Whiteladies Road', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS8 2PB', 'lat': 51.4640, 'lon': -2.6120},
            {'line1': '42 Gloucester Road', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS7 8AD', 'lat': 51.4770, 'lon': -2.5850},
            {'line1': '78 Cotham Hill', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS6 6LF', 'lat': 51.4680, 'lon': -2.6010},
            {'line1': '23 Stokes Croft', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS1 3PY', 'lat': 51.4605, 'lon': -2.5880},
            {'line1': '56 Clifton Village', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS8 4EJ', 'lat': 51.4560, 'lon': -2.6170},
            {'line1': '89 Redland Road', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS6 6QE', 'lat': 51.4700, 'lon': -2.6060},
            {'line1': '34 Easton Road', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS5 6QX', 'lat': 51.4650, 'lon': -2.5630},
            {'line1': '12 Bedminster Parade', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS3 4AG', 'lat': 51.4420, 'lon': -2.5910},
            {'line1': '5 Southville Road', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS3 1AD', 'lat': 51.4430, 'lon': -2.6120},
            {'line1': '27 Fishponds Road', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS16 3UH', 'lat': 51.4790, 'lon': -2.5360},
            {'line1': '18 Kingswood High Street', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS15 4AR', 'lat': 51.4590, 'lon': -2.5070},
            {'line1': '9 Bradley Stoke Way', 'city': 'Bristol', 'county': 'Somerset', 'postcode': 'BS32 8AW', 'lat': 51.5290, 'lon': -2.5420},
            {'line1': '44 Bath Road', 'city': 'Bath', 'county': 'Somerset', 'postcode': 'BA1 3EH', 'lat': 51.3770, 'lon': -2.3600},
        ]
        
        phone_prefixes = ['07710', '07720', '07730', '07800', '07810', '07900']
        
        self.stdout.write(self.style.SUCCESS('Creating mock customers...'))
        
        created_count = 0
        
        for i in range(15):  # Create 15 customers
            username = f"demo_customer{i+1}"
            email = f"demo_customer{i+1}@example.com"
            
            # Skip if already exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(f"Skipping {username} - already exists"))
                continue
            
            # Get random address data
            addr_data = random.choice(customer_addresses)
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password='123',
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                role=User.Role.CUSTOMER,
                phone_number=f"{random.choice(phone_prefixes)} {random.randint(100, 999)} {random.randint(100, 999)}",
            )
            
            # Create customer profile - properly unpack the tuple
            profile, created = CustomerProfile.objects.get_or_create(
                user=user,
            )

            # Create default address
            address = Address.objects.create(
                user=user,
                address_line1=addr_data['line1'],
                address_line2=f"Apt {random.randint(1, 20)}" if random.choice([True, False]) else '',
                city=addr_data['city'],
                county=addr_data['county'],
                post_code=addr_data['postcode'],
                country='UK',
                address_type='home',
                is_default=True,
                latitude=Decimal(str(addr_data['lat'])),
                longitude=Decimal(str(addr_data['lon'])),
            )

            # Create a cart for the customer - now using the actual profile instance
            Cart.objects.create(
                customer=profile,
            )
                        
            created_count += 1
            self.stdout.write(self.style.SUCCESS(f"  Created customer: {user.username} at {addr_data['postcode']}"))
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} customers!'))