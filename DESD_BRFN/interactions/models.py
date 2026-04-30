from django.db import models


class UserInteraction(models.Model):
    PRODUCT_VIEWED = 'product_viewed'
    ADDED_TO_CART = 'added_to_cart'
    PURCHASED = 'purchased'
    RECOMMENDATION_CLICKED = 'recommendation_clicked'
    QUALITY_SCAN = 'quality_scan'
    RECOMMENDATION_SERVED = 'recommendation_served'

    INTERACTION_TYPES = [
        (PRODUCT_VIEWED, 'Product Viewed'),
        (ADDED_TO_CART, 'Added to Cart'),
        (PURCHASED, 'Purchased'),
        (RECOMMENDATION_CLICKED, 'Recommendation Clicked'),
        (QUALITY_SCAN, 'Quality Scan'),
        (RECOMMENDATION_SERVED, 'Recommendation Served'),
    ]

    user = models.ForeignKey(
        'mainApp.RegularUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interactions',
    )
    session_key = models.CharField(max_length=40, blank=True)
    interaction_type = models.CharField(max_length=30, choices=INTERACTION_TYPES, db_index=True)
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interactions',
    )
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['interaction_type', 'timestamp']),
        ]

    def __str__(self):
        user_label = self.user.username if self.user else 'anon'
        product_label = self.product.name if self.product else '—'
        return f"{user_label} | {self.interaction_type} | {product_label}"
