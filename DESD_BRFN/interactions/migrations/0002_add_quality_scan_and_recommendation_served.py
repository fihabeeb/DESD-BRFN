from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('interactions', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userinteraction',
            name='interaction_type',
            field=models.CharField(
                choices=[
                    ('product_viewed', 'Product Viewed'),
                    ('added_to_cart', 'Added to Cart'),
                    ('purchased', 'Purchased'),
                    ('recommendation_clicked', 'Recommendation Clicked'),
                    ('quality_scan', 'Quality Scan'),
                    ('recommendation_served', 'Recommendation Served'),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
    ]
