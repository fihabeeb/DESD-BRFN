from django.db import models
from django.utils import timezone
from django.template.defaultfilters import slugify
from products.utility import product_image_path

class Product(models.Model):
    '''
    Product model for marketplace
    '''
    # Definitions
    MONTH_CHOICES = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December'),
    ]

    AVAILABILITY_CHOICES = [
    # ('in_season', 'In Season'),
    ('available', 'Available'),
    # ('out_of_season', 'Out of Season'),
    ('unavailable', 'Unavailable'),
    ]

    # Table information
    name=models.CharField(max_length=100, help_text="Product name") # maybe create this null= false
    description = models.TextField(help_text="Detailed product description")
    price = models.DecimalField(max_digits=8, decimal_places=2, help_text="Price per unit") # same with this
    unit = models.CharField(max_length=50, help_text="e.g., kg, dozen, each") # same
    stock_quantity = models.PositiveIntegerField(default=0, help_text="Current stock level")

    slug = models.SlugField(unique=True, blank=True)

    producer = models.ForeignKey(
        'mainApp.ProducerProfile',
        on_delete=models.PROTECT,
        related_name='products',
        null=True,
        blank=True,
    )

    availability = models.CharField(
        max_length=20,
        choices=AVAILABILITY_CHOICES,
        default='available',
        help_text='is this product available for purchase?'
    )


    harvest_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_organic = models.BooleanField(default=False)

    season_start = models.IntegerField(choices=MONTH_CHOICES, null=True, blank=True)
    season_end = models.IntegerField(choices=MONTH_CHOICES, null=True, blank=True)

    # media
    image = models.ImageField(upload_to=product_image_path,null=True,blank=True, help_text="Product image")

    category = models.ForeignKey(
        'ProductCategory',
        on_delete=models.SET_NULL,
        null=True,
        related_name='products',
        help_text='Product category'
    )

    # Allergen information
    allergens = models.ManyToManyField(
        "Allergen",
        blank=True,
        related_name='products',
        help_text="Select all allergens present in this product"
    )
    allergen_statement = models.TextField(
        blank=True,
        help_text="Additional allergen information or preparation notes (e.g., 'May contain traces of nuts due to shared equipment')"
    )
    has_allergens= models.BooleanField(default=False,help_text="Does this product contain any allergens?")
    allergen_notes = models.CharField(
        max_length=255,
        blank=True,
        help_text="Brief allergen warning for quick display")
    

    # handle soft delete fields
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="False if product has been soft deleted (hidden from store but kept for historical orders)"
    )

    deleted_at = models.DateTimeField(
        null=True, 
        blank=True,
        default=None,
        editable=False,
        help_text="Timestamp when product was soft deleted"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "product"
        verbose_name_plural = "products"

        # unique_together = ['name', 'producer']

        ordering = ['category', 'name']

        # allow quicker queries
        indexes = [
            models.Index(fields=['name'])
        ]

        # check contraints of fields
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name='price_non_negative'
            ),
            models.CheckConstraint(
                condition=models.Q(stock_quantity__gte=0),
                name='stock_non_negative'
            ),
        ]

    def deduct_stock(self, quantity):
        if self.stock_quantity >= quantity:
            self.stock_quantity -= quantity
            self.save(update_fields=['stock_quantity'])
            return True
        return False

    def save(self, *args, **kwargs):
        try:
            # Check if this is an existing product being updated
            if self.pk:
                old_product = Product.objects.get(pk=self.pk)
                
                # If there was an old image and it's different from the new one
                if old_product.image and old_product.image != self.image:
                    old_product.image.delete(save=False) 
        except Product.DoesNotExist:
            pass

        if not self.slug:
            self.slug = slugify(self.name)
            original_slug = self.slug
            counter = 1
            while Product.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1

        # allergen
        if not self.allergen_notes and self.pk:
            allergen_list = self.allergens.all()
            if allergen_list:
                self.has_allergens = True
                names = [a.get_name_display() for a in allergen_list]
                if len(names) > 3:
                    self.allergen_notes = f"Contains: {', '.join(names[:3])} and others"
                else:
                    self.allergen_notes = f"Contains: {', '.join(names)}"
            else:
                self.has_allergens = False
                self.allergen_notes = "No common allergens"

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        force = kwargs.pop('force', False)
        if force:
            self.hard_delete()
        else:
            self.soft_delete()

    def soft_delete(self):
        """Soft delete the product - hides from store but keeps for order history"""
        self.is_active = False
        self.deleted_at = timezone.now()
        self.availability = 'unavailable'
        self.save(update_fields=['is_active', 'deleted_at', 'availability'])

    def hard_delete(self):
        """Permanently delete the product (use with caution!)"""
        if self.image:
            self.image.delete(save=False)
        super().delete()

    @property
    def is_in_season(self):
        """
        Check if product is currently in season based on season_start and season_end.
        Returns True if:
        - No season dates set (always in season)
        - Current month falls within season range
        """
        if not (self.season_start and self.season_end):
            return True  # No season restriction = always in season
        
        current_month = timezone.now().month
        
        if self.season_start <= self.season_end:
            return self.season_start <= current_month <= self.season_end
        else:
            return current_month >= self.season_start or current_month <= self.season_end

    @property
    def is_available(self):
        """
        Combined availability: product must be both available AND in season
        This is what should be shown to customers
        """
        return self.availability == 'available'


    @property
    def is_low_stock(self):
        return 0 < self.stock_quantity < 10


    def get_food_miles(self, user_lat, user_long):
        """
        TC-013: Distance in miles from the producer's farm to Bristol city centre.
        Returns None if the producer has no geocoded location.
        """
        from mainApp.utils import haversine_miles, BRISTOL_LAT, BRISTOL_LON
        producer = self.producer
        if not producer or not producer.latitude or not producer.longitude:
            return None
        
        if user_lat is not None and user_long is not None:
            lat, lon = user_lat, user_long
        else:
            lat, lon = BRISTOL_LAT, BRISTOL_LON

        return round(haversine_miles(producer.latitude, producer.longitude, lat, lon), 1)
    
    @property
    def allergen_display(self):
        if not self.has_allergens:
            return "No common allergens"

        allergen_list = self.allergens.all()
        if not allergen_list:
            return "No common allergens"
        
        return f"Contatins: {', '.join([a.get_name_display() for a in allergen_list])}"

class ProductCategory(models.Model):
    '''
    Product categories
    '''

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    slug = models.SlugField(unique=True) # for urls path
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)

    order = models.PositiveIntegerField(default=0) # can be used to rank the ranking of the categories.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "product category"
        verbose_name_plural = "product categories"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    ### Functions
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) # set url path to use the name of the category
        super().save(*args, **kwargs)


# =============================================================================
# TC-019 — Surplus / Last-Minute Deals
# =============================================================================

class SurplusDeal(models.Model):
    """
    A time-limited discount applied to a product to reduce food waste.
    Created by producers; expires automatically via a scheduled job.
    """

    product = models.OneToOneField(
        'Product',
        on_delete=models.CASCADE,
        related_name='surplus_deal'
    )
    producer = models.ForeignKey(
        'mainApp.ProducerProfile',
        on_delete=models.CASCADE,
        related_name='surplus_deals'
    )

    discount_percent = models.PositiveIntegerField(
        help_text="Discount between 10 and 50 percent inclusive"
    )
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    discounted_price = models.DecimalField(max_digits=10, decimal_places=2)

    note = models.CharField(
        max_length=500,
        blank=True,
        help_text="e.g. 'Perfect condition, must sell quickly'"
    )
    best_before_date = models.DateField(null=True, blank=True)
    expires_at = models.DateTimeField(help_text="When this deal automatically expires")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(discount_percent__gte=10),
                name='surplus_discount_min'
            )
        ]

    def save(self, *args, **kwargs):
        from decimal import Decimal
        # Auto-calculate discounted price
        self.discounted_price = (
            self.original_price * (1 - Decimal(self.discount_percent) / 100)
        ).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"{self.discount_percent}% off {self.product.name} (expires {self.expires_at:%d %b %Y %H:%M})"


class Allergen(models.Model):
    """
    TC-015 & TC-03 allergen information
    """
    ALLERGEN_CHOICES = [
        ('celery', 'Celery'),
        ('cereals_gluten', 'Cereals containing gluten (wheat, rye, barley, oats)'),
        ('crustaceans', 'Crustaceans (prawns, crabs, lobster)'),
        ('eggs', 'Eggs'),
        ('fish', 'Fish'),
        ('lupin', 'Lupin'),
        ('milk', 'Milk'),
        ('molluscs', 'Molluscs (mussels, oysters, snails)'),
        ('mustard', 'Mustard'),
        ('nuts', 'Nuts (almonds, hazelnuts, walnuts, etc.)'),
        ('peanuts', 'Peanuts'),
        ('sesame', 'Sesame seeds'),
        ('soya', 'Soya'),
        ('sulphites', 'Sulphur dioxide / sulphites'),
    ]

    name = models.CharField(max_length=50, choices=ALLERGEN_CHOICES, unique=True)
    display_name = models.CharField(max_length=100, help_text="Display name for the allergen")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name
    
    class Meta:
        ordering = ['name']
        verbose_name = "allergen"
        verbose_name_plural = "allergens"

    def get_name_display(self):
        return self.display_name

# class ProductReview(models.Model):
#     # TODO



    # user class should have a one to one extension
    # - helps maintain 1 unique username and email per user
    # - a producer can be a buyer and vice versa