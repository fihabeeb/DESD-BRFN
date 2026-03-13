# producer/management/commands/seed_producers_simple.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from mainApp.models import ProducerProfile
import random
from django.utils import timezone
from datetime import timedelta
from django.db.utils import IntegrityError

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed producer table with mock data (simple version)'

    def handle(self, *args, **options):
        try:
            username="demo_admin"
            if not User.objects.filter(username=username).exists():
                user =User.objects.create_superuser(username=username,email=None,password="123")

                self.stdout.write(f"  Created admin: {user.username}")
        except IntegrityError as e:
            print (f"{e}: Use already exist")
            