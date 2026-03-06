# producer/management/commands/seed_producers_simple.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from mainApp.models import ProducerProfile
import random
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed producer table with mock data (simple version)'

    def handle(self, *args, **options):
        # Sample data lists
        first_names = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emma', 'Robert', 'Lisa', 
                      'William', 'Anna', 'James', 'Maria', 'Thomas', 'Susan', 'Paul', 'Karen']
        
        last_names = ['Smith', 'Jones', 'Williams', 'Brown', 'Taylor', 'Davies', 'Evans', 'Wilson',
                     'Thomas', 'Johnson', 'Roberts', 'Walker', 'Wright', 'Robinson', 'Thompson', 'White']
        
        farm_names = ['Green Acres', 'Sunny Meadow', 'Valley View', 'Oak Tree', 'River Bend',
                     'Happy Hens', 'Organic Oasis', 'Heritage Harvest', 'Wildflower', 'Pasture Prime',
                     'Golden Grain', 'Blue Sky', 'Red Barn', 'Misty Morning', 'Country Gardens']
        
        cities = ['Bristol', 'Bath', 'Wells', 'Weston-super-Mare', 'Clevedon', 'Portishead',
                 'Yate', 'Keynsham', 'Thornbury', 'Bradford-on-Avon', 'Frome', 'Radstock']
        
        postcodes = ['BS1 1AB', 'BS2 8EF', 'BS3 4GH', 'BS4 2JK', 'BS5 6LM', 'BS6 7NP',
                    'BS7 9QR', 'BS8 3ST', 'BS9 5UV', 'BA1 2WX', 'BA2 4YZ', 'BA3 6CD']
        
        counties = ['Somerset', 'Gloucestershire', 'Avon', 'Wiltshire']
        
        self.stdout.write(self.style.SUCCESS('Creating mock producers...'))
        
        for i in range(4):  # Create 20 producers
            username = f"demo_producer{i+1}"
            email = f"demo_producer{i+1}@example.com"
            
            # Skip if already exists
            if User.objects.filter(username=username).exists() or User.objects.filter(email=email).exists():
                continue
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password='123',
                first_name=random.choice(first_names),
                last_name=random.choice(last_names),
                role=User.Role.PRODUCER,
                phone_number=f"07700 900{random.randint(100, 999)}",
                address=f"{random.randint(1, 100)} High Street",
                post_code=random.choice(postcodes),
            )
            
            # Create producer profile
            profile = ProducerProfile.objects.create(
                user=user,
                company_name=random.choice(farm_names),
            #     farm_description=f"A family-run farm providing fresh, local produce to the {random.choice(cities)} area.",
            #     farm_address=f"{random.randint(1, 50)} Farm Lane",
            #     farm_city=random.choice(cities),
            #     farm_postcode=random.choice(postcodes),
            #     farm_county=random.choice(counties),
            #     website=f"www.{username}.farm" if random.choice([True, False]) else '',
            #     phone=user.phone_number,
            #     delivery_options=','.join(random.sample(['collection', 'local_delivery', 'national_delivery'], 
            #                                            random.randint(1, 3))),
            #     delivery_radius=random.choice([5, 10, 15, 20, 30]),
            #     minimum_order=random.choice([0, 5, 10, 15, 20]),
            #     lead_time_hours=random.choice([24, 48, 72]),
            #     accepts_returns=random.choice([True, False]),
            #     is_verified=random.choice([True, False]),
            #     total_sales=random.randint(0, 10000),
            #     total_orders=random.randint(0, 500),
            #     joined_at=timezone.now() - timedelta(days=random.randint(30, 365)),
            )
            
            self.stdout.write(f"  Created producer: {user.username} - {profile}")
        
        # self.stdout.write(self.style.SUCCESS('Mock producers created successfully!'))