from django.db import models
from products.models import Product, ProductCategory
from django.utils import timezone
from django import forms
from products.models import Allergen, Product
from django.forms import CheckboxInput #
import os

ALLOWED_MB_IMAGE = 5 # this will be used for the allowed image size to accept

class ProductForm(forms.ModelForm):
    """
    Form for producers to add/edit products (TC-003)
    """

    allergen_list = forms.ModelMultipleChoiceField(
        queryset=Allergen.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'allergen-checkbox'}),
        required=False,
        label="Allergens",
        help_text="Select all allergens present in this product"
    )

    class Meta:
        model = Product
        fields = [
            'name', 'description', 'category', 'price', 'unit', 
            'stock_quantity', 'availability', 'is_organic',
            'season_start', 'season_end', 'harvest_date', 'image',
            'allergen_list', 'allergen_statement',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Detailed product description...'}),
            'harvest_date': forms.DateInput(attrs={'type': 'date'}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'stock_quantity': forms.NumberInput(attrs={'min': '0'}),
            'allergen_statement': forms.Textarea(attrs={
                'rows': 2,
                "placeholder": 'E.g., "May contain traces of nuts due to shared equipment"',
                'class': 'form-control'
            }),
        }
        help_texts = {
            'season_start': 'Leave blank if available year-round',
            'season_end': 'Leave blank if available year-round',
            'unit': 'e.g., kg, dozen, 500g, each',
            'allergen_statement': 'Optional: Add any additional allergen warnings'
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
        self.fields['allergen_list'].required = False
        self.fields['allergen_statement'].required = False
        
        # Add CSS classes
        for field in self.fields:
            if field not in ['allergen_list', 'is_organic']:
                self.fields[field].widget.attrs.update({'class': 'form-control'})

        if self.instance and self.instance.pk:
            self.fields['allergen_list'].initial = self.instance.allergens.all()

    def clean(self):
        """Custom validation"""
        cleaned_data = super().clean()
        season_start = cleaned_data.get('season_start')
        season_end = cleaned_data.get('season_end')
        allergen_list = cleaned_data.get('allergen_list')
        allergen_statement = cleaned_data.get('allergen_statement')
        
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
                
        if allergen_list and not allergen_statement:
            # Not required, but we might want to encourage it
            cleaned_data['allergen_statement'] = f"Contains: {', '.join([a.get_name_display() for a in allergen_list])}"
        
        return cleaned_data
    
    def clean_image(self):
        image = self.cleaned_data.get('image')

        if not image:
            return image
        
        if image.size > ALLOWED_MB_IMAGE * 1024 * 1024:
            raise forms.ValidationError(f"Image file too large (max {ALLOWED_MB_IMAGE}MB)")
        
        # valid_types = ['image/jpeg', 'image/png', 'image/jpg']
        # if image.content_type not in valid_types:
        #     raise forms.ValidationError(f"Invalid file type. Allowed: {', '.join(valid_types)}")
        
        # ext = os.path.splitext(image.name)[1].lower()
        # valid_extensions = ['.jpg', '.jpeg', '.png']
        # if ext not in valid_extensions:
        #     raise forms.ValidationError(f"Invalid file extension. Allowed: {', '.join(valid_extensions)}")
        
        return image

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
        
        allergen_list = self.cleaned_data.get('allergen_list')
        product.has_allergens = bool(allergen_list and allergen_list.exists())

        if commit:
            product.save()

            # Set many-to-many allergens
            if allergen_list:
                product.allergens.set(allergen_list)
            else:
                product.allergens.clear()

            # Auto generate allergen notes
            if allergen_list:
                names = [a.get_name_display() for a in allergen_list]

                if len(names) > 3:
                    product.allergen_notes = f"Contains: {', '.join(names[:3])} and others"
                else:
                    product.allergen_notes = f"Contains: {', '.join(names)}"

            else:
                product.allergen_notes = "No common allergens"

            product.save(update_fields=['allergen_notes', 'has_allergens'])

        return product


# Scrapping the class below cuz idk how we want to store multiple images tbh

# class ProductImageForm(forms.Form):
#     '''
#     For multiple image uploads (experimenting)
#     '''
#     images = forms.ImageField(
#         widget=forms.ClearableFileInput(attrs={'multiple': True}),
#         required=False
#     )

#     def clean_images(self):
#         images = self.files.getlist('images')
        
#         if len(images) > 5:
#             raise forms.ValidationError("Maximum 5 images per product")
        
#         for image in images:
#             # Same validation as above for each image
#             if image.size > ALLOWED_MB_IMAGE * 1024 * 1024:
#                 raise forms.ValidationError(f"Each image must be less than {ALLOWED_MB_IMAGE}MB")
        
#         return images
    

