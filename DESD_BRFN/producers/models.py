from django.db import models
from django.contrib.auth.models import AbstractUser
from mainApp.models import RegularUser


# Create your models here.
#class ProducerUser(RegularUser):
#    #is_editor = models.BooleanField(default=False)
#    contact_name = models.CharField('Producer Contact',max_length=50)
#   producer_name = models.CharField('Producer',max_length=50)

# maybe tables for set orders and delivery
#class Post(models.Model):
#    title = models.CharField(max_length=100)
#    content = models.TextField()
#    author = models.ForeignKey(ProducerUser, on_delete=models.CASCADE)
