from django.db import models
from django.utils import timezone
from django.template.defaultfilters import slugify

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
    ('in_season', 'In Season'),
    ('available', 'Available'),
    ('out_of_season', 'Out of Season'),
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
        on_delete=models.SET_NULL,
        related_name='products',
        null=True,
        blank=True,
    )

    availability = models.CharField(
        max_length=20,
        choices=AVAILABILITY_CHOICES,
        default='available'
    )


    harvest_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_organic = models.BooleanField(default=False)

    season_start = models.IntegerField(choices=MONTH_CHOICES, null=True, blank=True)
    season_end = models.IntegerField(choices=MONTH_CHOICES, null=True, blank=True)

    # media
    image = models.ImageField(upload_to='products/',null=True,blank=True)

    # Relationships
    # TODO
    # producer id ig

    category = models.ForeignKey(
        'ProductCategory',
        on_delete=models.SET_NULL,
        null=True,
        related_name='products',
        help_text='Product category'
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

    ## extra attributes that idk if needed



    ### Functions
    ## TODO : in_season: check product in season or not.
    def in_season(self):
        if not(self.season_start and self.season_end):
            return True # assume always in season

        current_month = timezone.now().month

        if self.season_start <= self.season_end:
            # for normal season that doesn't overlap between Dec and Jan
            return self.season_start <= current_month <= self.season_end
        else:
            # specifically for winter
            return current_month >= self.season_start or current_month<= self.season_end

    def deduct_stock(self, quantity):
        if self.stock_quantity >= quantity:
            self.stock_quantity -= quantity
            self.save(update_fields=['stock_quantity'])
            return True
        return False

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            original_slug = self.slug
            counter = 1
            while Product.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def is_low_stock(self):
        return 0 < self.stock_quantity < 10

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

# class ProductReview(models.Model):
#     # TODO



    # user class should have a one to one extension
    # - helps maintain 1 unique username and email per user
    # - a producer can be a buyer and vice versa
