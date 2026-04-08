# mainApp/signals.py
from django.core.signals import request_finished
from django.dispatch import receiver
from mainApp.models import RegularUser, ProducerProfile, CustomerProfile
from django.db.models.signals import post_save, pre_delete, post_delete

@receiver(post_save, sender=RegularUser)
def create_profiles(sender, instance, created, **kwargs):

    if created:
        if instance.role == RegularUser.Role.PRODUCER:
            ProducerProfile.objects.get_or_create(user=instance)
        elif instance.role == RegularUser.Role.CUSTOMER:
            CustomerProfile.objects.get_or_create(user=instance)
        else:
            print("PLS UPDATE mainApp SIGNALS.py ")

    print("mainApp: Profile signal ran!")
    