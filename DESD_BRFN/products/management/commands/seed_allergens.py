from django.db import migrations
from products.models import Allergen
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed allergen table with mock data'

    def handle(self, *args, **options):

        allergens = [
            ("celery", "Celery"),
            ("cereals_gluten", "Cereals containing gluten"),
            ("crustaceans", "Crustaceans"),
            ("eggs", "Eggs"),
            ("fish", "Fish"),
            ("lupin", "Lupin"),
            ("milk", "Milk"),
            ("molluscs", "Molluscs"),
            ("mustard", "Mustard"),
            ("nuts", "Nuts"),
            ("peanuts", "Peanuts"),
            ("sesame", "Sesame seeds"),
            ("soya", "Soya"),
            ("sulphites", "Sulphur dioxide / sulphites"),
        ]

        for name, display in allergens:
            Allergen.objects.get_or_create(
                name=name,
                defaults={"display_name": display}
            )
            self.stdout.write(self.style.SUCCESS(f'Created Allergne called {name}'))

    # class Migration(migrations.Migration):

    #     dependencies = []

    #     operations = [
    #         migrations.RunPython(create_allergens)
    #     ]