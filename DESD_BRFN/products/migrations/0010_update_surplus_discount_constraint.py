"""
Remove the 50% upper-bound on SurplusDeal.discount_percent.
The new constraint only enforces a minimum of 10%.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0009_add_surplus_deal'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='surplusdeal',
            name='surplus_discount_range',
        ),
        migrations.AddConstraint(
            model_name='surplusdeal',
            constraint=models.CheckConstraint(
                condition=models.Q(discount_percent__gte=10),
                name='surplus_discount_min',
            ),
        ),
    ]
