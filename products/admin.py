from django.contrib import admin
from .models import Product, ProductCategory

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['order', 'name', 'parent', 'is_active', 'product_count']
    list_display_links = ['name']
    list_editable = ['order', 'is_active']

    list_filter = ['is_active', 'parent']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    actions = ['activate_categories', 'deactivate_categories']
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'
    
    def activate_categories(self, request, queryset):
        queryset.update(is_active=True)
    activate_categories.short_description = "Activate selected categories"
    
    def deactivate_categories(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_categories.short_description = "Deactivate selected categories"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'stock_quantity', 'availability', 'is_organic']
    list_filter = ['availability', 'is_organic', 'category', 'created_at']
    list_editable = ['price', 'stock_quantity', 'availability']  # Quick edits
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'image')
        }),
        ('Pricing & Stock', {
            'fields': ('price', 'unit', 'stock_quantity', 'availability')
        }),
        ('Seasonal & Organic', {
            'fields': ('is_organic', 'season_start', 'season_end', 'harvest_date'),
            'classes': ('collapse',)  # Collapsible section
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new product
            # can auto-set producer here 
            pass
        super().save_model(request, obj, form, change)