# mainApp/signals.py
from django.core.signals import request_finished
from django.dispatch import receiver
from mainApp.models import (
    RegularUser, ProducerProfile, CustomerProfile,
    CommunityMemberProfile, RestaurantProfile,
)
from django.db.models.signals import post_save, pre_delete, post_delete

@receiver(post_save, sender=RegularUser)
def create_profiles(sender, instance, created, **kwargs):

    if created:
        if instance.role == RegularUser.Role.PRODUCER:
            ProducerProfile.objects.get_or_create(user=instance)
        elif instance.role == RegularUser.Role.CUSTOMER:
            CustomerProfile.objects.get_or_create(user=instance)
        elif instance.role == RegularUser.Role.COMMUNITY_MEMBER:
            CommunityMemberProfile.objects.get_or_create(user=instance)
        elif instance.role == RegularUser.Role.RESTAURANT:
            RestaurantProfile.objects.get_or_create(
                user=instance,
                defaults={'business_name': instance.get_full_name() or instance.username}
            )

        print("mainApp__create_profiles: Signal ran!")
    