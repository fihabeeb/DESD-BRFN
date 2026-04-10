from django.db import models
from django.contrib.auth.models import AbstractUser
from mainApp.models import RegularUser


# =============================================================================
# TC-020 — Producer Recipes & Farm Stories
# =============================================================================

MODERATION_STATUS_CHOICES = [
    ('pending', 'Pending Review'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]

SEASONAL_TAG_CHOICES = [
    ('spring', 'Spring'),
    ('summer', 'Summer'),
    ('autumn', 'Autumn'),
    ('winter', 'Winter'),
    ('year_round', 'Year Round'),
]


class Recipe(models.Model):
    """
    A recipe created by a producer, optionally linked to their products.
    Must be approved before appearing publicly.
    """

    producer = models.ForeignKey(
        'mainApp.ProducerProfile',
        on_delete=models.CASCADE,
        related_name='recipes'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    ingredients = models.TextField(help_text="One ingredient per line, or free text")
    instructions = models.TextField(help_text="Step-by-step cooking instructions")
    image = models.ImageField(upload_to='recipes/', null=True, blank=True)

    seasonal_tags = models.CharField(
        max_length=100,
        blank=True,
        help_text="Comma-separated tags, e.g. 'autumn,winter'"
    )

    # Link to products this recipe uses (from the producer's own catalogue)
    linked_products = models.ManyToManyField(
        'products.Product',
        blank=True,
        related_name='recipes'
    )

    moderation_status = models.CharField(
        max_length=20,
        choices=MODERATION_STATUS_CHOICES,
        default='pending'
    )
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if self.is_published and self.moderation_status == 'approved' and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class FarmStory(models.Model):
    """
    A farm story / blog post created by a producer.
    Must be approved before appearing publicly.
    """

    producer = models.ForeignKey(
        'mainApp.ProducerProfile',
        on_delete=models.CASCADE,
        related_name='farm_stories'
    )
    title = models.CharField(max_length=255)
    body = models.TextField(help_text="Rich text story body")

    moderation_status = models.CharField(
        max_length=20,
        choices=MODERATION_STATUS_CHOICES,
        default='pending'
    )
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if self.is_published and self.moderation_status == 'approved' and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)


class FarmStoryImage(models.Model):
    """Multiple images for a FarmStory."""

    story = models.ForeignKey(FarmStory, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='farm_stories/')
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']


class SavedRecipe(models.Model):
    """TC-020: Customers can bookmark recipes."""

    customer = models.ForeignKey(
        RegularUser,
        on_delete=models.CASCADE,
        related_name='saved_recipes'
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='saved_by'
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('customer', 'recipe')
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.customer.username} saved '{self.recipe.title}'"


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
