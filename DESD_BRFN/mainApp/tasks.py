from celery import shared_task
from django.apps import apps

@shared_task
def geocode_address_async(address_id):
    try:
        Address = apps.get_model('mainApp', 'Address')
        address = Address.objects.get(id=address_id)
        _ = address.geocode()
        address.save(skip_geocoding=True)  # Prevent recursion
    except Address.DoesNotExist:
        pass