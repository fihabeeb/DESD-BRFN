from django import forms
from django.contrib.auth import get_user_model
from mainApp.models import ProducerProfile, Address
from mainApp.utils import geocode_postcode
import logging
import re

logger = logging.getLogger(__name__)
User = get_user_model()


# class ProducerPersonalInfoForm(forms.ModelForm):
#     """
#     Form for editing producer personal, business, and farm information.
#     All fields are optional so the user can update only one field at a time.
#     """

#     # Business info
#     business_name = forms.CharField(required=False)

#     # Farm address fields
#     farm_address_line1 = forms.CharField(required=False)
#     farm_address_line2 = forms.CharField(required=False)
#     farm_city = forms.CharField(required=False)
#     farm_county = forms.CharField(required=False)
#     farm_post_code = forms.CharField(required=False)

#     # Password
#     password1 = forms.CharField(
#         required=False,
#         widget=forms.PasswordInput(),
#         help_text="Leave blank to keep your current password."
#     )
#     password2 = forms.CharField(
#         label="Confirm Password",
#         widget=forms.PasswordInput,
#         )

#     class Meta:
#         model = User
#         fields = [
#             "username",
#             "email",
#             "first_name",
#             "last_name",
#             "phone_number",
#         ]

#     def __init__(self, *args, **kwargs):
#         self.user = kwargs.pop("user")
#         super().__init__(*args, **kwargs)

#         # Make all fields optional
#         for field in self.fields.values():
#             field.required = False

#         # Disable username and email fields - they cannot be changed
#         self.fields['username'].widget.attrs['readonly'] = True
#         self.fields['username'].help_text = "Username cannot be changed"
#         self.fields['username'].initial = self.user.username
        
#         self.fields['email'].widget.attrs['readonly'] = True
#         self.fields['email'].help_text = "Email cannot be changed. Contact support if you need to update it."
#         self.fields['email'].initial = self.user.email

        
#         # Add helpful tooltips
#         self.fields['first_name'].widget.attrs['placeholder'] = "First name"
#         self.fields['last_name'].widget.attrs['placeholder'] = "Last name"
#         self.fields['phone_number'].widget.attrs['placeholder'] = "Phone number"
#         self.fields['business_name'].widget.attrs['placeholder'] = "Farm/Business name"
        

#         # Load producer profile
#         profile = getattr(self.user, "producer_profile", None)

#         # Load farm address
#         farm = self.user.addresses.filter(address_type="farm", is_default=True).first()

#         # Pre-fill extra fields from related models
#         if profile:
#             self.fields["business_name"].initial = profile.business_name

#         if farm:
#             self.fields["farm_address_line1"].initial = farm.address_line1
#             self.fields["farm_address_line2"].initial = farm.address_line2
#             self.fields["farm_city"].initial = farm.city
#             self.fields["farm_county"].initial = farm.county
#             self.fields["farm_post_code"].initial = farm.post_code

#     def clean_username(self):
#         """Prevent username from being changed"""
#         if self.cleaned_data.get('username') != self.user.username:
#             raise forms.ValidationError("Username cannot be changed.")
#         return self.user.username

#     def clean_email(self):
#         """Prevent email from being changed"""
#         if self.cleaned_data.get('email') != self.user.email:
#             raise forms.ValidationError("Email cannot be changed. Contact support for email updates.")
#         return self.user.email
    
#     def clean(self):
#         cleaned_data = super().clean()
#         cleaned_data['username'] = self.user.username
#         cleaned_data['email'] = self.user.email

#         password1 = cleaned_data.get('password1')
#         password2 = cleaned_data.get('password2')
        
#         # Only validate if password is being changed
#         if password1 or password2:
#             if not password1:
#                 self.add_error('password1', "Please enter a new password.")
#             elif not password2:
#                 self.add_error('password2', "Please confirm your password.")
#             elif password1 != password2:
#                 self.add_error('password2', "Passwords do not match.")
#             elif len(password1) < 8:
#                 self.add_error('password1', "Password must be at least 8 characters long.")
#             # Optional: Add more password strength checks
#             elif password1.isdigit():
#                 self.add_error('password1', "Password cannot be entirely numeric.")
#             elif password1.lower() in ['password', 'password123', '12345678']:
#                 self.add_error('password1', "Password is too common. Please choose a stronger password.")
        
#         return cleaned_data

#     def save(self, commit=True):
#         """
#         IMPORTANT: This must update self.user, not create a new one.
#         """
#         user = self.user  # always work on the existing logged-in user

#         # Update only changed user fields
#         for field in ["first_name", "last_name", "phone_number"]:
#             if field in self.cleaned_data:
#                 new_value = self.cleaned_data[field]
#                 if new_value != "" and new_value != getattr(user, field):
#                     setattr(user, field, new_value)

#         # Update password if provided
#         password1 = self.cleaned_data.get("password1")
#         password2 = self.cleaned_data.get("password2")
#         if password1 and password2 and password1 == password2:
#             user.set_password(password1)

#         if commit:
#             user.save()

#             # Ensure producer profile exists
#             profile, _ = ProducerProfile.objects.get_or_create(user=user)

#             # Update business name
#             if self.cleaned_data.get("business_name"):
#                 profile.business_name = self.cleaned_data["business_name"]

#             # Ensure farm address exists
#             farm = user.addresses.filter(address_type="farm", is_default=True).first()
#             # Get or create farm address
#             farm = user.addresses.filter(address_type="farm", is_default=True).first()
#             farm_created = False
#             if not farm:
#                 farm = Address.objects.create(
#                     user=user,
#                     address_line1="",
#                     city="",
#                     post_code="",
#                     country="UK",
#                     address_type="farm",
#                     is_default=True
#                 )
#                 farm_created = True

#             mapping = {
#                 "farm_address_line1": "address_line1",
#                 "farm_address_line2": "address_line2",
#                 "farm_city": "city",
#                 "farm_county": "county",
#                 "farm_post_code": "post_code",
#             }

#             postcode_changed = False
#             any_field_updated = False

#             for form_field, model_field in mapping.items():
#                 if form_field in self.cleaned_data:
#                     new_value = self.cleaned_data[form_field]
#                     if new_value != "" and new_value != getattr(farm, model_field):
#                         setattr(farm, model_field, new_value)
#                         any_field_updated = True
#                         if form_field == "farm_post_code":
#                             postcode_changed = True

#             # Only geocode if fields were updated AND we have a postcode
#             if any_field_updated and farm.post_code:
#                 # Geocode the farm address
#                 lat, lon = geocode_postcode(farm.post_code)
#                 if lat and lon:
#                     profile.latitude = lat
#                     profile.longitude = lon
#                     farm.latitude = lat
#                     farm.longitude = lon
#                 farm.save()
#                 profile.save()
#             elif any_field_updated:
#                 # Save even without geocoding
#                 farm.save()
#                 if farm_created:
#                     profile.save()

#         return user


# producers/forms.py
from django import forms
from django.contrib.auth import get_user_model
from mainApp.models import ProducerProfile, Address
from mainApp.utils import geocode_postcode
import re
import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class ProducerPersonalInfoForm(forms.Form):  # Changed to forms.Form (not ModelForm)
    """
    Form for editing producer personal, business, and farm information.
    Username and email are handled separately in the template.
    """

    # Personal fields (username and email removed)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    phone_number = forms.CharField(required=False)

    # Business info
    business_name = forms.CharField(required=False)

    # Farm address fields
    farm_address_line1 = forms.CharField(required=False)
    farm_address_line2 = forms.CharField(required=False)
    farm_city = forms.CharField(required=False)
    farm_county = forms.CharField(required=False)
    farm_post_code = forms.CharField(required=False)

    # Password
    password1 = forms.CharField(
        required=False,
        widget=forms.PasswordInput(),
        help_text="Leave blank to keep your current password."
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

        # Make all fields optional
        for field in self.fields.values():
            field.required = False

        # Add placeholders
        self.fields['first_name'].widget.attrs['placeholder'] = "First name"
        self.fields['last_name'].widget.attrs['placeholder'] = "Last name"
        self.fields['phone_number'].widget.attrs['placeholder'] = "Phone number"
        self.fields['business_name'].widget.attrs['placeholder'] = "Farm/Business name"

        # Load producer profile
        profile = getattr(self.user, "producer_profile", None)

        # Load farm address
        farm = self.user.addresses.filter(address_type="farm", is_default=True).first()

        # Pre-fill extra fields from related models
        if profile:
            self.fields["business_name"].initial = profile.business_name

        if farm:
            self.fields["farm_address_line1"].initial = farm.address_line1
            self.fields["farm_address_line2"].initial = farm.address_line2
            self.fields["farm_city"].initial = farm.city
            self.fields["farm_county"].initial = farm.county
            self.fields["farm_post_code"].initial = farm.post_code

    def clean_phone_number(self):
        """Validate phone number format"""
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Basic phone validation (adjust pattern as needed)
            phone_pattern = r'^[0-9\s\+\-\(\)]{10,}$'
            if not re.match(phone_pattern, phone):
                raise forms.ValidationError("Please enter a valid phone number.")
        return phone

    def clean_farm_post_code(self):
        """Validate UK postcode format"""
        post_code = self.cleaned_data.get('farm_post_code')
        if post_code:
            # UK postcode validation
            uk_postcode_pattern = r'^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$'
            if not re.match(uk_postcode_pattern, post_code.upper()):
                raise forms.ValidationError("Please enter a valid UK postcode.")
            return post_code.upper()
        return post_code

    def clean(self):
        """Validate password fields"""
        cleaned_data = super().clean()
        
        # Password validation
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        # Only validate if password is being changed
        if password1 or password2:
            if not password1:
                self.add_error('password1', "Please enter a new password.")
            elif not password2:
                self.add_error('password2', "Please confirm your password.")
            elif password1 != password2:
                self.add_error('password2', "Passwords do not match.")
            elif len(password1) < 8:
                self.add_error('password1', "Password must be at least 8 characters long.")
            elif password1.isdigit():
                self.add_error('password1', "Password cannot be entirely numeric.")
            elif password1.lower() in ['password', 'password123', '12345678']:
                self.add_error('password1', "Password is too common. Please choose a stronger password.")
        
        return cleaned_data

    def _update_farm_address(self):
        """Handle farm address creation/update"""
        farm = self.user.addresses.filter(address_type="farm", is_default=True).first()
        
        farm_data = {
            'address_line1': self.cleaned_data.get('farm_address_line1', ''),
            'address_line2': self.cleaned_data.get('farm_address_line2', ''),
            'city': self.cleaned_data.get('farm_city', ''),
            'county': self.cleaned_data.get('farm_county', ''),
            'post_code': self.cleaned_data.get('farm_post_code', ''),
            'country': 'UK',
        }
        
        has_data = any(farm_data.values())
        
        if not has_data:
            return None
        
        if farm:
            updated = False
            for key, value in farm_data.items():
                if value != getattr(farm, key):
                    setattr(farm, key, value)
                    updated = True
            if updated:
                farm.save()
            return farm
        else:
            farm = Address.objects.create(
                user=self.user,
                address_type='farm',
                is_default=True,
                **farm_data
            )
            return farm

    def _geocode_farm_address(self, farm_address):
        """Geocode address and update coordinates"""
        if not farm_address or not farm_address.post_code:
            return False
        
        try:
            lat, lon = geocode_postcode(farm_address.post_code)
            if lat and lon:
                farm_address.latitude = lat
                farm_address.longitude = lon
                farm_address.save()
                
                profile = getattr(self.user, "producer_profile", None)
                if profile:
                    profile.latitude = lat
                    profile.longitude = lon
                    profile.save()
                return True
        except Exception as e:
            logger.error(f"Geocoding failed: {e}")
        
        return False

    def save(self, commit=True):
        """Save all form data"""
        user = self.user

        # Update user fields
        user_fields = ["first_name", "last_name", "phone_number"]
        for field in user_fields:
            new_value = self.cleaned_data.get(field)
            # Allow clearing optional fields, but don't overwrite with None
            if new_value is not None and new_value != getattr(user, field):
                setattr(user, field, new_value)

        # Update password if provided
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 == password2:
            user.set_password(password1)

        if commit:
            user.save()

            # Update profile
            profile, _ = ProducerProfile.objects.get_or_create(user=user)
            business_name = self.cleaned_data.get("business_name")
            if business_name:
                profile.business_name = business_name
                profile.save()

            # Handle farm address
            farm_address = self._update_farm_address()
            if farm_address and farm_address.post_code:
                self._geocode_farm_address(farm_address)

        return user