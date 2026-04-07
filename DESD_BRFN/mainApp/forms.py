# mainApp/forms.py
from django import forms
from mainApp.models import Address
import re
from django.contrib.auth import get_user_model

User = get_user_model()

class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            'label', 'address_type', 'address_line1', 'address_line2',
            'city', 'county', 'post_code', 'country', 'is_default'
        ]
        widgets = {
            'address_line1': forms.TextInput(attrs={'placeholder': 'Street address'}),
            'address_line2': forms.TextInput(attrs={'placeholder': 'Apartment, suite, etc.'}),
            'city': forms.TextInput(attrs={'placeholder': 'City/Town'}),
            'county': forms.TextInput(attrs={'placeholder': 'County (optional)'}),
            'post_code': forms.TextInput(attrs={'placeholder': 'Post Code'}),
            'country': forms.TextInput(attrs={'placeholder': 'Country'}),
            'label': forms.TextInput(attrs={'placeholder': 'e.g., "Work", "Mum\'s House"'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['address_type'].required = True

        if not self.instance.pk:
            self.fields['address_line1'].required = True
            self.fields['city'].required = True
            self.fields['post_code'].required = True

        if self.user and hasattr(self.user, 'role'):
            if self.user.role == 'customer':
                allowed = ['home', 'shipping', 'billing', 'business']
                self.fields['address_type'].choices = [
                    c for c in self.fields['address_type'].choices
                    if c[0] in allowed
                ]

            elif self.user.role == 'producer':
                has_farm = Address.objects.filter(
                    user=self.user, address_type='farm'
                ).exists()

                if not has_farm:
                    # No farm yet — lock to farm only
                    self.fields['address_type'].choices = [('farm', 'Farm')]
                    self.fields['address_type'].initial = 'farm'
                    self.fields['address_type'].widget.attrs['disabled'] = True
                    self.fields['address_type'].help_text = (
                        "You must add your farm address before adding other address types."
                    )
                else:
                    # Has farm — hide farm from dropdown but keep it valid for existing farm edits
                    non_farm = [
                        c for c in self.fields['address_type'].choices
                        if c[0] != 'farm'
                    ]

                    # If editing an existing farm address, add farm back as a hidden option
                    # so the form renders and validates correctly
                    editing_farm = (
                        self.instance.pk and self.instance.address_type == 'farm'
                    )

                    if editing_farm:
                        self.fields['address_type'].choices = [('farm', 'Farm')] + non_farm
                        self.fields['address_type'].widget.attrs['disabled'] = True
                        self.fields['address_type'].help_text = (
                            "Farm address type cannot be changed."
                        )
                    else:
                        self.fields['address_type'].choices = non_farm

    def clean_post_code(self):
        post_code = self.cleaned_data.get('post_code')
        if post_code:
            pattern = r'^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$'
            if not re.match(pattern, post_code.upper()):
                raise forms.ValidationError("Please enter a valid UK postcode.")
            return post_code.upper()
        return post_code
    
    def clean_address_type(self):
        address_type = self.cleaned_data.get('address_type')

        if self.user and self.user.role == 'producer':
            has_farm = Address.objects.filter(
                user=self.user, address_type='farm'
            ).exists()

            # Disabled fields aren't submitted by the browser
            # so restore the correct value from the instance or force 'farm'
            if not address_type:
                if self.instance.pk:
                    return self.instance.address_type  # editing existing — restore original
                return 'farm'  # new address, no farm yet — must be farm

            # Block producers from manually submitting 'farm' on a new address
            # if they already have one (catches anyone bypassing the UI)
            if address_type == 'farm' and has_farm and not self.instance.pk:
                raise forms.ValidationError(
                    "You already have a farm address. Producers can only have one."
                )

        return address_type
    
    def clean_is_default(self):
        """Validate default address based on user role"""
        is_default = self.cleaned_data.get('is_default')
        address_type = self.cleaned_data.get('address_type')
        
        # If this is a producer trying to set a non-farm address as default
        if is_default and self.user and self.user.role == 'producer':
            if address_type != 'farm':
                # Get the farm address to show in message
                farm_address = self.user.addresses.filter(address_type='farm').first()
                if farm_address:
                    raise forms.ValidationError(
                        f"Producers must have a farm address as default. "
                        f"Your farm address is: {farm_address.address_line1}, {farm_address.city}. "
                    )
                else:
                    raise forms.ValidationError(
                        "Producers must have a farm address as default. "
                        "Please add a farm address first."
                    )
        
        return is_default
    
    def save(self, commit=True):
        """
        Save the address, ensuring only one default per address type.
        This is the key fix for the IntegrityError.
        """
        address = super().save(commit=False)
        
        # If this address is being set as default, unset any existing default of the same type
        if address.is_default and address.address_type:
            # Find and unset the current default of this type
            Address.objects.filter(
                user=address.user,
                address_type=address.address_type,
                is_default=True
            ).exclude(pk=address.pk if address.pk else None).update(is_default=False)
        
        if commit:
            address.save()
        
        return address

    # Remove the clean() default-unsetting logic entirely —
    # the model's save() handles this reliably