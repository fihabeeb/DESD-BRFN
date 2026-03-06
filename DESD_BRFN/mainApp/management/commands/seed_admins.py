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
        user =User.objects.create_superuser('demo_admin',email=None,password="123")

        self.stdout.write(f"  Created admin: {user.username}")