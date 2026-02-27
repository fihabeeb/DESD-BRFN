from django.db import models
from django.contrib.auth.models import AbstractUser


# Create your models here.
# class ProducerUser(AbstractUser):
#     #is_editor = models.BooleanField(default=False)
#     contact_name = models.CharField('Producer Contact',max_length=50)
#     producer_name = models.CharField('Producer',max_length=50)
#     phone_number = models.CharField(max_length=100)
#     password = models.CharField(max_length=100)
#     email = models.EmailField(max_length=255)
#     address = models.CharField(max_length=20)
#     post_code = models.CharField(max_length=20)
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

# maybe tables for set orders and delivery
#class Post(models.Model):
#    title = models.CharField(max_length=100)
#    content = models.TextField()
#    author = models.ForeignKey(ProducerUser, on_delete=models.CASCADE)
