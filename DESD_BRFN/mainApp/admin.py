from django.contrib import admin
from .models import (
    RegularUser, Address, CustomerProfile, ProducerProfile,
    CommunityMemberProfile, RestaurantProfile, SystemAdminProfile,
)


@admin.register(RegularUser)
class RegularUserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']


@admin.register(CommunityMemberProfile)
class CommunityMemberProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'organisation_name', 'charity_or_education_status', 'is_verified']
    list_filter = ['charity_or_education_status', 'is_verified']
    list_editable = ['is_verified']
    search_fields = ['organisation_name', 'user__username', 'user__email']


@admin.register(RestaurantProfile)
class RestaurantProfileAdmin(admin.ModelAdmin):
    list_display = ['business_name', 'user', 'business_registration_number', 'is_verified']
    list_filter = ['is_verified']
    list_editable = ['is_verified']
    search_fields = ['business_name', 'user__username']
