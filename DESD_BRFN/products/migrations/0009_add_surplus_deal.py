"""
TC-019: Add SurplusDeal model
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_alter_product_producer'),
        ('mainApp', '0017_add_restaurant_role_and_profiles'),
    ]

    operations = [
        migrations.CreateModel(
            name='SurplusDeal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('discount_percent', models.PositiveIntegerField(
                    help_text='Discount between 10 and 50 percent inclusive',
                )),
                ('original_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('discounted_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('note', models.CharField(
                    blank=True,
                    help_text="e.g. 'Perfect condition, must sell quickly'",
                    max_length=500,
                )),
                ('best_before_date', models.DateField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(help_text='When this deal automatically expires')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='surplus_deal',
                    to='products.product',
                )),
                ('producer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='surplus_deals',
                    to='mainApp.producerprofile',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='surplusdeal',
            constraint=models.CheckConstraint(
                condition=models.Q(discount_percent__gte=10, discount_percent__lte=50),
                name='surplus_discount_range',
            ),
        ),
    ]
