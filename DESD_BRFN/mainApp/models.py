from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth.models import AbstractUser


class RegularUser(AbstractUser):
    #Inherits: username, first_name, last_name, email, is_staff, is_active, date_joined, password, last_login
    class Role(models.TextChoices):
        CUSTOMER = 'customer'
        PRODUCER = 'producer'
        COMMUNITY_MEMBER = 'community_member'
        SYSTEM_ADMIN = 'system_admin'

    role = models.CharField(max_length=20, choices=Role.choices)
    phone_number = models.CharField(max_length=100)
    address = models.CharField(max_length=20)
    post_code = models.CharField(max_length=20)
    # created_at = models.DateTimeField(auto_now_add=True) # DONT UNCOMMENT: Already has date_joined 
    updated_at = models.DateTimeField(auto_now=True)


#class CustomerProfile(models.Model):
#   user = models.OneToOneField(RegularUser, on_delete=models.CASCADE, related_name='customer_profile')
#    # customer-specific fields
#    shipping_address = models.TextField(blank=True)
    # ...

class ProducerProfile(models.Model):
    user = models.OneToOneField(RegularUser, on_delete=models.CASCADE, related_name='producer_profile')
    # producer-specific fields
    company_name = models.CharField(max_length=200)
    # ...

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
