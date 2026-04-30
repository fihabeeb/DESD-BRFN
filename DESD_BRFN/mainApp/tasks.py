from celery import shared_task
from django.apps import apps

@shared_task
def geocode_address_async(address_id):
    return
# try:
#     print('running geocoding async')
#     Address = apps.get_model('mainApp', 'Address')
#     address = Address.objects.get(id=address_id)
#     result = address.geocode()
#     if result:
#         address.save(skip_geocoding=True, skip_default_handling=True)  # Prevent recursion
# except Address.DoesNotExist:
#     pass