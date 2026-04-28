from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from mainApp.tasks import geocode_address_async
from mainApp.utils import haversine_miles, geocode_postcode
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.db import transaction
from django.utils import timezone

import logging

logger = logging.getLogger(__name__)
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
        on_delete=models.SET_NULL,
        null=True,
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
                fields=['user', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_address_per_user'
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
    
    @property
    def is_producer(self):
        """Check if the user associated with this address is a producer"""
        return hasattr(self.user, 'role') and self.user.role == 'producer'
    
    def get_coordinates(self):
        '''
        retunr latitude and longitude
        '''
        return self.latitude, self.longitude
    
    def geocode(self):
        """Geocode the address and update coordinates"""   
        try:
            lat, lon = geocode_postcode(self.post_code)
            if lat and lon:
                self.latitude = lat
                self.longitude = lon
                return True
        except Exception as e:
            print("GEOCODE ERROR:", e)
        
        return False
        
    def _enforce_producer_default_farm(self):
        """
        For producers, ensure the default address is always a farm type.
        If trying to set a non-farm address as default, it will be rejected
        and a farm address will be promoted instead.
        """
        if not self.is_producer:
            return
        
        # If this is a non-farm address trying to be set as default
        if self.is_default and self.address_type != 'farm':
            # Check if there's a farm address that can be default instead
            farm_address = Address.objects.filter(
                user=self.user,
                address_type='farm'
            ).first()
            
            if farm_address:
                # Promote the farm address to default
                farm_address.is_default = True
                farm_address.save(update_fields=['is_default'])
                logger.info(
                    f"Producer {self.user.username} attempted to set non-farm address as default. "
                    f"Farm address {farm_address.id} set as default instead."
                )
                # Prevent this non-farm address from being default
                self.is_default = False
            else:
                # No farm address exists, so we can't set any default
                self.is_default = False
                logger.warning(
                    f"Producer {self.user.username} has no farm address. "
                    f"Cannot set non-farm address as default."
                )
    

    def save(self, *args, **kwargs):
        skip_default_handling = kwargs.pop('skip_default_handling', False)
        skip_geocoding = kwargs.pop('skip_geocoding', False)
        
        is_new = not self.pk
        address_type = self.address_type

        # ==========================================
        # 2. POSTCODE AND GEOCODING
        # ==========================================
        old_postcode = None
        if not is_new and not skip_geocoding:
            try:
                old_postcode = Address.objects.only('post_code').get(pk=self.pk).post_code
            except Address.DoesNotExist:
                old_postcode = None

        # ==========================================
        # 3. HANDLE DEFAULT ADDRESS UNIQUENESS
        # ==========================================
        # Only handle default uniqueness if not skipped
        if not skip_default_handling and self.is_default:
            # Unset all other defaults of the same type
            Address.objects.filter(
                user=self.user,
                address_type=address_type,
                is_default=True
            ).exclude(pk=self.pk if not is_new else None).update(is_default=False)

        # ==========================================
        # 4. SAVE THE ADDRESS
        # ==========================================
        super().save(*args, **kwargs)

        if not skip_geocoding and self.post_code:
            needs_geocoding = is_new
            if not is_new and old_postcode is not None:
                needs_geocoding = old_postcode != self.post_code
            
            if needs_geocoding:
                # pass # for testing
                geocode_address_async.delay(self.pk)


    def delete(self, *args, **kwargs):
        # Prevent deleting last farm address for producers
        if self.is_producer and self.address_type == 'farm':
            remaining = Address.objects.filter(
                user=self.user,
                address_type='farm'
            ).exclude(pk=self.pk).count()
            if remaining == 0:
                raise ValidationError(
                    "You must keep at least one farm address."
                )

        was_default = self.is_default
        address_type = self.address_type
        user = self.user

        super().delete(*args, **kwargs)

        # Promote next address if default was deleted
        if was_default:
            next_address = Address.objects.filter(
                user=user,
                address_type=address_type
            ).order_by('-created_at').first()
            if next_address:
                Address.objects.filter(pk=next_address.pk).update(is_default=True)


class RegularUser(AbstractUser):
    #Inherits: username, first_name, last_name, email, is_staff, is_active, date_joined, password, last_login
    class Role(models.TextChoices):
        CUSTOMER = 'customer'
        PRODUCER = 'producer'
        COMMUNITY_MEMBER = 'community_member'
        RESTAURANT = 'restaurant'
        SYSTEM_ADMIN = 'system_admin'

    role = models.CharField(max_length=20, choices=Role.choices)
    phone_number = models.CharField(max_length=100)
    post_code = models.CharField(max_length=20)
    # created_at = models.DateTimeField(auto_now_add=True) # DONT UNCOMMENT: Already has date_joined 
    updated_at = models.DateTimeField(auto_now=True)

    # soft delete attributes
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True, default=None)

    @property
    def default_address(self):
        return self.addresses.filter(is_default=True).first()
    
    @property
    def default_address_postcode(self):
        address = self.addresses.filter(is_default=True).first()
        return address.post_code
    
    @property
    def default_shipping_address(self):
        """Get user's default shipping address"""
        return self.addresses.filter(address_type='shipping', is_default=True).first()
    
    @property
    def default_billing_address(self):
        """Get user's default billing address"""
        return self.addresses.filter(address_type='billing', is_default=True).first()
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None
    
    def get_default_address_coordinates(self):
        '''
        return latitude and longtitude
        '''
        address = self.addresses.filter(is_default=True).first()
        if not address:
            return None, None
        return address.get_coordinates()
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def soft_delete(self):
        """
        Soft delete user and anonymize personal data
        
        Currently not in use, cant decide if i wanna use this or not tbh - aliff
        """
        # Don't delete, just anonymize
        self.is_active = False
        self.deleted_at = timezone.now()
        
        # Anonymize personal data (keep for order history but not identifiable)
        original_username = self.username
        self.username = f"deleted_user_{self.id}"
        self.email = f"deleted_{self.id}@deleted.local"
        self.first_name = ""
        self.last_name = ""
        self.phone_number = ""
        
        # Save without triggering signals that might affect orders
        super().save(update_fields=[
            'is_active', 'deleted_at', 'deletion_reason', 'is_anonymized',
            'username', 'email', 'first_name', 'last_name', 'phone_number'
        ])
        
        # Soft delete profiles
        if hasattr(self, 'customer_profile'):
            self.customer_profile.soft_delete()
        if hasattr(self, 'producer_profile'):
            self.producer_profile.soft_delete()
    
    # def delete(self, *args, **kwargs):
    #     super().delete(*args, **kwargs)
    #     force = kwargs.pop('force', False)
    #     if force:
    #         self.hard_delete()
    #     else:
    #         self.soft_delete()

    # def soft_delete(self):
    #     """Soft delete the user"""
    #     self.is_active = False
    #     self.deleted_at = timezone.now()
    #     self.availability = 'unavailable'
    #     self.save(update_fields=['is_active', 'deleted_at', 'availability'])

    # def hard_delete(self):
    #     """Permanently delete the user (use with caution!)"""
    #     if self.image:
    #         self.image.delete(save=False)
    #     super().delete()




class CustomerProfile(models.Model):
    user = models.OneToOneField(RegularUser, on_delete=models.CASCADE, related_name='customer_profile')


    def soft_delete(self):
        pass

    # customer-specific fields

    # Moving address to master table
    # shipping_address = models.TextField(blank=True,null=True)
    # ...

class ProducerProfile(models.Model):
    user = models.OneToOneField(RegularUser, on_delete=models.SET_NULL, null=True, related_name='producer_profile')
    # producer-specific fields
    business_name = models.CharField(max_length=200)
    lead_time_hours = models.PositiveIntegerField(
        default=48,
        help_text="Minimum hours notice required before delivery"
    )

    def __str__(self):
        return f"{self.business_name} ({self.user.get_full_name()})"

    # TC-013 food miles — set automatically from user.post_code via postcodes.io on registration
    # ALIFF: use the address table 
    # latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    # longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    @property
    def farm_address(self):
        return self.user.addresses.filter(address_type='farm', is_default=True).first()
    
    @property
    def latitude(self):
        """Get latitude from farm address"""
        farm = self.farm_address
        return farm.latitude if farm else None
    
    @property
    def longitude(self):
        """Get longitude from farm address"""
        farm = self.farm_address
        return farm.longitude if farm else None
    
    def soft_delete(self):
        pass

class CommunityMemberProfile(models.Model):
    """TC-017: Community group / organisation profile (schools, charities, etc.)"""

    CHARITY_EDUCATION_CHOICES = [
        ('charity', 'Charity'),
        ('education', 'Educational Institution'),
        ('other', 'Other Community Organisation'),
    ]

    user = models.OneToOneField(RegularUser, on_delete=models.CASCADE, related_name='community_member_profile')
    # community member-specific fields
    bio = models.TextField(blank=True)

    # TC-017 organisation fields
    organisation_name = models.CharField(max_length=255, blank=True, help_text="Name of school, charity, or organisation")
    charity_or_education_status = models.CharField(
        max_length=20,
        choices=CHARITY_EDUCATION_CHOICES,
        blank=True,
        help_text="Type of community organisation"
    )
    institutional_email = models.EmailField(
        blank=True,
        help_text="Official institutional email address for verification"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Admin-verified community group account"
    )

    def __str__(self):
        return self.organisation_name or self.user.username


class RestaurantProfile(models.Model):
    """TC-018: Restaurant / business account profile"""

    user = models.OneToOneField(RegularUser, on_delete=models.CASCADE, related_name='restaurant_profile')
    business_name = models.CharField(max_length=255)
    business_registration_number = models.CharField(max_length=100, blank=True, help_text="VAT or company registration number")
    is_verified = models.BooleanField(default=False, help_text="Admin-approved business account")
    default_payment_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="Stripe payment method ID for automated charges"
    )

    def __str__(self):
        return self.business_name


class SystemAdminProfile(models.Model):
    user = models.OneToOneField(RegularUser, on_delete=models.CASCADE, related_name='system_admin_profile')
    # admin-specific fields
    admin_level = models.IntegerField(default=1)
    # ...

