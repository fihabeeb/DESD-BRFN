"""
TC-017 & TC-018:
  - Add RESTAURANT to RegularUser.role choices
  - Extend CommunityMemberProfile with organisation fields
  - Add RestaurantProfile model
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mainApp', '0016_alter_producerprofile_user'),
    ]

    operations = [
        # ── RegularUser.role: add 'restaurant' choice ──────────────────────────
        migrations.AlterField(
            model_name='regularuser',
            name='role',
            field=models.CharField(
                choices=[
                    ('customer', 'Customer'),
                    ('producer', 'Producer'),
                    ('community_member', 'Community Member'),
                    ('restaurant', 'Restaurant'),
                    ('system_admin', 'System Admin'),
                ],
                max_length=20,
            ),
        ),

        # ── CommunityMemberProfile: new organisation fields ────────────────────
        migrations.AddField(
            model_name='communitymemberprofile',
            name='organisation_name',
            field=models.CharField(
                blank=True,
                help_text='Name of school, charity, or organisation',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='communitymemberprofile',
            name='charity_or_education_status',
            field=models.CharField(
                blank=True,
                choices=[
                    ('charity', 'Charity'),
                    ('education', 'Educational Institution'),
                    ('other', 'Other Community Organisation'),
                ],
                help_text='Type of community organisation',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='communitymemberprofile',
            name='institutional_email',
            field=models.EmailField(
                blank=True,
                help_text='Official institutional email address for verification',
            ),
        ),
        migrations.AddField(
            model_name='communitymemberprofile',
            name='is_verified',
            field=models.BooleanField(
                default=False,
                help_text='Admin-verified community group account',
            ),
        ),

        # ── RestaurantProfile ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='RestaurantProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('business_name', models.CharField(max_length=255)),
                ('business_registration_number', models.CharField(
                    blank=True,
                    help_text='VAT or company registration number',
                    max_length=100,
                )),
                ('is_verified', models.BooleanField(
                    default=False,
                    help_text='Admin-approved business account',
                )),
                ('default_payment_method', models.CharField(
                    blank=True,
                    help_text='Stripe payment method ID for automated charges',
                    max_length=50,
                )),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='restaurant_profile',
                    to='mainApp.regularuser',
                )),
            ],
        ),
    ]
