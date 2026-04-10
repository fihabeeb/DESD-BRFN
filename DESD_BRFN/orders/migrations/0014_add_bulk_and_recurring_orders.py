"""
TC-017 & TC-018:
  - Add special_instructions to OrderPayment
  - Add is_bulk_order to OrderProducer
  - Add RecurringOrder, RecurringOrderItem, OrderInstance, OrderInstanceItem
"""
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0013_alter_orderpayment_shipping_address_id'),
        ('mainApp', '0017_add_restaurant_role_and_profiles'),
        ('products', '0008_alter_product_producer'),
    ]

    operations = [
        # ── OrderPayment: special_instructions ────────────────────────────────
        migrations.AddField(
            model_name='orderpayment',
            name='special_instructions',
            field=models.TextField(
                blank=True,
                help_text="e.g. 'Delivery to kitchen entrance, contact kitchen manager'",
            ),
        ),

        # ── OrderProducer: is_bulk_order ────────────────────────────────────
        migrations.AddField(
            model_name='orderproducer',
            name='is_bulk_order',
            field=models.BooleanField(
                default=False,
                help_text='Marked automatically when ordered by a community group account',
            ),
        ),

        # ── RecurringOrder ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='RecurringOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('active', 'Active'),
                        ('paused', 'Paused'),
                        ('cancelled', 'Cancelled'),
                    ],
                    default='active',
                    max_length=20,
                )),
                ('recurrence', models.CharField(
                    choices=[
                        ('weekly', 'Weekly'),
                        ('fortnightly', 'Fortnightly'),
                    ],
                    default='weekly',
                    max_length=20,
                )),
                ('recurrence_day', models.CharField(
                    choices=[
                        ('monday', 'Monday'), ('tuesday', 'Tuesday'),
                        ('wednesday', 'Wednesday'), ('thursday', 'Thursday'),
                        ('friday', 'Friday'), ('saturday', 'Saturday'),
                        ('sunday', 'Sunday'),
                    ],
                    help_text='Day the order is triggered',
                    max_length=10,
                )),
                ('delivery_day', models.CharField(
                    choices=[
                        ('monday', 'Monday'), ('tuesday', 'Tuesday'),
                        ('wednesday', 'Wednesday'), ('thursday', 'Thursday'),
                        ('friday', 'Friday'), ('saturday', 'Saturday'),
                        ('sunday', 'Sunday'),
                    ],
                    help_text='Expected delivery day',
                    max_length=10,
                )),
                ('delivery_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('next_scheduled_date', models.DateField(blank=True, null=True)),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recurring_orders',
                    to='mainApp.regularuser',
                )),
                ('delivery_address', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recurring_orders',
                    to='mainApp.address',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),

        # ── RecurringOrderItem ──────────────────────────────────────────────
        migrations.CreateModel(
            name='RecurringOrderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_name', models.CharField(max_length=255)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('unit', models.CharField(blank=True, max_length=50)),
                ('recurring_order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='orders.recurringorder',
                )),
                ('product', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recurring_items',
                    to='products.product',
                )),
                ('producer', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='mainApp.producerprofile',
                )),
            ],
        ),

        # ── OrderInstance ───────────────────────────────────────────────────
        migrations.CreateModel(
            name='OrderInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scheduled_date', models.DateField()),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending Review'),
                        ('confirmed', 'Confirmed'),
                        ('modified', 'Modified'),
                        ('cancelled', 'Cancelled'),
                        ('processed', 'Processed'),
                    ],
                    default='pending',
                    max_length=20,
                )),
                ('notification_sent', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('recurring_order', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='instances',
                    to='orders.recurringorder',
                )),
                ('order_payment', models.OneToOneField(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='recurring_instance',
                    to='orders.orderpayment',
                )),
            ],
            options={'ordering': ['-scheduled_date']},
        ),

        # ── OrderInstanceItem ───────────────────────────────────────────────
        migrations.CreateModel(
            name='OrderInstanceItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_name', models.CharField(max_length=255)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('unit', models.CharField(blank=True, max_length=50)),
                ('instance', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items',
                    to='orders.orderinstance',
                )),
                ('product', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='instance_items',
                    to='products.product',
                )),
            ],
        ),
    ]
