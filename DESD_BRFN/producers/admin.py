from django.contrib import admin
from .models import Recipe, FarmStory, FarmStoryImage, SavedRecipe


class FarmStoryImageInline(admin.TabularInline):
    model = FarmStoryImage
    extra = 0


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['title', 'producer', 'moderation_status', 'is_published', 'created_at']
    list_filter = ['moderation_status', 'is_published', 'created_at']
    list_editable = ['moderation_status', 'is_published']
    search_fields = ['title', 'producer__business_name']
    filter_horizontal = ['linked_products']
    readonly_fields = ['created_at', 'updated_at', 'published_at']


@admin.register(FarmStory)
class FarmStoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'producer', 'moderation_status', 'is_published', 'created_at']
    list_filter = ['moderation_status', 'is_published', 'created_at']
    list_editable = ['moderation_status', 'is_published']
    search_fields = ['title', 'producer__business_name']
    readonly_fields = ['created_at', 'updated_at', 'published_at']
    inlines = [FarmStoryImageInline]


@admin.register(SavedRecipe)
class SavedRecipeAdmin(admin.ModelAdmin):
    list_display = ['customer', 'recipe', 'saved_at']
    list_filter = ['saved_at']
    search_fields = ['customer__username', 'recipe__title']
