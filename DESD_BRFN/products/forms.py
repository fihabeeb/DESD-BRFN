from django.db import models
from products.models import Product, ProductCategory
from django.utils import timezone
from django import forms

class ProductForm(forms.ModelForm):
    """
    Form for producers to add/edit products (TC-003)
    """
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'category', 'price', 'unit', 
            'stock_quantity', 'availability', 'is_organic',
            'season_start', 'season_end', 'harvest_date', 'image',
            # Allergen information would go here if you add it to model
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Detailed product description...'}),
            'harvest_date': forms.DateInput(attrs={'type': 'date'}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'stock_quantity': forms.NumberInput(attrs={'min': '0'}),
        }
        help_texts = {
            'season_start': 'Leave blank if available year-round',
            'season_end': 'Leave blank if available year-round',
            'unit': 'e.g., kg, dozen, 500g, each',
        }

    def __init__(self, *args, **kwargs):
        self.producer = kwargs.pop('producer', None)
        super().__init__(*args, **kwargs)
        
        # Filter categories to only show active ones
        self.fields['category'].queryset = ProductCategory.objects.filter(is_active=True)
        
        # Make some fields optional
        self.fields['season_start'].required = False
        self.fields['season_end'].required = False
        self.fields['harvest_date'].required = False
        self.fields['image'].required = False
        
        # Add CSS classes
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

    def clean(self):
        """Custom validation"""
        cleaned_data = super().clean()
        season_start = cleaned_data.get('season_start')
        season_end = cleaned_data.get('season_end')
        
        # If one season field is set, both should be set
        if (season_start and not season_end) or (not season_start and season_end):
            raise forms.ValidationError(
                "Both season start and end must be set together, or leave both blank for year-round availability."
            )
        
        # Validate season range
        if season_start and season_end:
            if season_start > season_end:
                # Check if it's a winter season (Dec-Jan)
                if not (season_start == 12 and season_end == 1):
                    raise forms.ValidationError(
                        "Season end must be after season start, except for winter seasons (Dec-Jan)."
                    )
        
        return cleaned_data

    def save(self, commit=True):
        product = super().save(commit=False)
        
        # Set the producer
        if self.producer:
            product.producer = self.producer
        
        # Auto-set availability based on season if not manually set
        if not product.availability and product.season_start and product.season_end:
            current_month = timezone.now().month
            if product.season_start <= current_month <= product.season_end:
                product.availability = 'in_season'
            else:
                product.availability = 'out_of_season'
        
        if commit:
            product.save()
            # Handle many-to-many relationships if any
            
        return product

