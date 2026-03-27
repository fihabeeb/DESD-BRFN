from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver

'''
TC-022
As a system administrator, I want to ensure secure authentication so
that user accounts and data are protected.


User roles exist: Customer, Producer, Community Group, Restaurant, Admin
'''

class Address(models.Model):
    ADDRESS_TYPES = [
        ('home', 'Home'),
        ('shipping', 'Shipping'),
        ('billing', 'Billing'),
        ('farm', 'Farm'),
        ('business', 'Business'),
    ]

    user = models.ForeignKey(
        "RegularUser",
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    label = models.CharField(max_length=50, blank=True, help_text="e.g 'Mum's house', 'Business'")

    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    county = models.CharField(max_length=100, blank=True)
    post_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default='UK')

    # System to fill this up:
    # TC 013 foodmile
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES, default='home')
    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Addresses"
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'address_type', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_address'
            )
        ]

    def __str__(self):
        parts = [self.address_line1, self.city, self.post_code]
        return ", ".join(filter(None, parts))
    
    @property
    def full_address(self):
        """Return formatted full address"""
        lines = [self.address_line1]
        if self.address_line2:
            lines.append(self.address_line2)
        lines.extend([self.city, self.county, self.post_code, self.country])
        return ", ".join(filter(None, lines))  

    def save(self, *args, **kwargs):
        # If this is the user's first address of this type, make it default automatically
        if not self.pk:  # only on creation
            existing = Address.objects.filter(
                user=self.user,
                address_type=self.address_type
            ).exists()
            if not existing:
                self.is_default = True

        # existing logic — unset other defaults if this one is default
        if self.is_default:
            Address.objects.filter(
                user=self.user,
                address_type=self.address_type,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        was_default = self.is_default
        address_type = self.address_type
        user = self.user

        super().delete(*args, **kwargs)

        # If we just deleted the default, promote the most recent remaining address
        if was_default:
            next_address = Address.objects.filter(
                user=user,
                address_type=address_type
            ).order_by('-created_at').first()

            if next_address:
                next_address.is_default = True
                next_address.save()


class RegularUser(AbstractUser):
    #Inherits: username, first_name, last_name, email, is_staff, is_active, date_joined, password, last_login
    class Role(models.TextChoices):
        CUSTOMER = 'customer'
        PRODUCER = 'producer'
        COMMUNITY_MEMBER = 'community_member'
        SYSTEM_ADMIN = 'system_admin'

    role = models.CharField(max_length=20, choices=Role.choices)
    phone_number = models.CharField(max_length=100)
    post_code = models.CharField(max_length=20)
    # created_at = models.DateTimeField(auto_now_add=True) # DONT UNCOMMENT: Already has date_joined 
    updated_at = models.DateTimeField(auto_now=True)

    # Moving address to master table
    # address = models.CharField(max_length=20)
    # post_code = models.CharField(max_length=20)

    @property
    def default_address(self):
        return self.addresses.filter(is_default=True).first()
    
    @property
    def default_shipping_address(self):
        """Get user's default shipping address"""
        return self.addresses.filter(address_type='shipping', is_default=True).first()
    
    @property
    def default_billing_address(self):
        """Get user's default billing address"""
        return self.addresses.filter(address_type='billing', is_default=True).first()

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"



class CustomerProfile(models.Model):
    user = models.OneToOneField(RegularUser, on_delete=models.CASCADE, related_name='customer_profile')
    # customer-specific fields

    # Moving address to master table
    # shipping_address = models.TextField(blank=True,null=True)
    # ...

class ProducerProfile(models.Model):
    user = models.OneToOneField(RegularUser, on_delete=models.CASCADE, related_name='producer_profile')
    # producer-specific fields
    business_name = models.CharField(max_length=200)

    # TC-013 food miles — set automatically from user.post_code via postcodes.io on registration
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    @property
    def farm_address(self):
        return self.user.addresses.filter(address_type='farm', is_default=True).first()

class CommunityMemberProfile(models.Model):
    user = models.OneToOneField(RegularUser, on_delete=models.CASCADE, related_name='community_member_profile')
    # community member-specific fields
    bio = models.TextField(blank=True)
    # ...

class SystemAdminProfile(models.Model):
    user = models.OneToOneField(RegularUser, on_delete=models.CASCADE, related_name='system_admin_profile')
    # admin-specific fields
    admin_level = models.IntegerField(default=1)
    # ...


    
@receiver(post_save, sender=RegularUser)
def create_profiles(sender, instance, created, **kwargs):
    if created:
        if instance.role == RegularUser.Role.PRODUCER:
            ProducerProfile.objects.get_or_create(user=instance)
        elif instance.role == RegularUser.Role.CUSTOMER:
            CustomerProfile.objects.get_or_create(user=instance)