"""
TC-020: Add Recipe, FarmStory, FarmStoryImage, SavedRecipe models
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('producers', '0002_delete_produceruser'),
        ('mainApp', '0017_add_restaurant_role_and_profiles'),
        ('products', '0009_add_surplus_deal'),
    ]

    operations = [
        # ── Recipe ─────────────────────────────────────────────────────────
        migrations.CreateModel(
            name='Recipe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('ingredients', models.TextField(help_text='One ingredient per line, or free text')),
                ('instructions', models.TextField(help_text='Step-by-step cooking instructions')),
                ('image', models.ImageField(blank=True, null=True, upload_to='recipes/')),
                ('seasonal_tags', models.CharField(
                    blank=True,
                    help_text="Comma-separated tags, e.g. 'autumn,winter'",
                    max_length=100,
                )),
                ('moderation_status', models.CharField(
                    choices=[
                        ('pending', 'Pending Review'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('is_published', models.BooleanField(default=False)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('producer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recipes',
                    to='mainApp.producerprofile',
                )),
                ('linked_products', models.ManyToManyField(
                    blank=True,
                    related_name='recipes',
                    to='products.product',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),

        # ── FarmStory ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='FarmStory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('body', models.TextField(help_text='Rich text story body')),
                ('moderation_status', models.CharField(
                    choices=[
                        ('pending', 'Pending Review'),
                        ('approved', 'Approved'),
                        ('rejected', 'Rejected'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('is_published', models.BooleanField(default=False)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('producer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='farm_stories',
                    to='mainApp.producerprofile',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),

        # ── FarmStoryImage ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='FarmStoryImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='farm_stories/')),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('order', models.PositiveIntegerField(default=0)),
                ('story', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='images',
                    to='producers.farmstory',
                )),
            ],
            options={'ordering': ['order']},
        ),

        # ── SavedRecipe ─────────────────────────────────────────────────────
        migrations.CreateModel(
            name='SavedRecipe',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('saved_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saved_recipes',
                    to='mainApp.regularuser',
                )),
                ('recipe', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saved_by',
                    to='producers.recipe',
                )),
            ],
            options={
                'ordering': ['-saved_at'],
                'unique_together': {('customer', 'recipe')},
            },
        ),
    ]
