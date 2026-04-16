from django.contrib import admin
from django.urls import path
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from . import views

class InsightsAdmin(admin.ModelAdmin):
    """
    A dummy admin class used only to create a top-level 'Insights' section
    with custom pages.
    """

    # We override get_urls to add our custom admin pages
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', self.admin_site.admin_view(views.insights_index), name='insights_index'),
            path('recommendations/', self.admin_site.admin_view(views.recommendation_insights), name='insights_recommendations'),
            path('classification/', self.admin_site.admin_view(views.classification_insights), name='insights_classification'),
        ]
        return custom_urls + urls

    # Hide the dummy model from the model list
    def has_module_permission(self, request):
        return True  # show the section
    def has_view_permission(self, request, obj=None):
        return True
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


# Register a dummy model to create the section
from django.db import models

class InsightsDummy(models.Model):
    class Meta:
        verbose_name = "Insights"
        verbose_name_plural = "Insights"
        app_label = "insights"

admin.site.register(InsightsDummy, InsightsAdmin)
