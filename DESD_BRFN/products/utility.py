import os
from uuid import uuid4
from django.utils import timezone
from django.conf import settings

def product_image_path(instance, filename):
    '''
    generate file path for product image
    '''

    extension = filename.split('.')[-1].lower()

    timestamp = timezone.now().strftime('%y%m%d_%H$M$S')
    unique_id = uuid4().hex[:4]

    product_id =instance.id or 'temp'
    dev_prefix = settings.DEV_NAME if settings.DEBUG else 'default'

    return f"products/{dev_prefix}/{product_id}/{timestamp}_{unique_id}.{extension}"