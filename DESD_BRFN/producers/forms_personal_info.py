from django import forms
from django.contrib.auth import get_user_model
from mainApp.models import ProducerProfile
import re

User = get_user_model()


class ProducerPersonalInfoForm(forms.Form):
    """
    Form for editing producer personal and business info.
    Addresses are managed separately in the address management section.
    """
    
    # Personal fields
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    phone_number = forms.CharField(required=False)

    # Business fields
    business_name = forms.CharField(required=False)

    # Password
    password1 = forms.CharField(
        required=False,
        widget=forms.PasswordInput(),
        label="New Password",
        help_text="Leave blank to keep your current password."
    )
    password2 = forms.CharField(
        required=False,
        widget=forms.PasswordInput(),
        label="Confirm Password",
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

        # Load existing data for display
        profile = getattr(self.user, "producer_profile", None)
        if profile:
            self.fields['business_name'].initial = profile.business_name

    def clean_phone_number(self):
        """Validate phone number format"""
        phone = self.cleaned_data.get('phone_number')
        if phone:
            phone_pattern = r'^[0-9\s\+\-\(\)]{10,}$'
            if not re.match(phone_pattern, phone):
                raise forms.ValidationError("Please enter a valid phone number.")
        return phone

    def clean(self):
        """Validate password fields"""
        cleaned_data = super().clean()
        
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
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
        
        return cleaned_data

    def save(self, commit=True):
        """Save the form data"""
        user = self.user

        # Update user fields
        user_fields = ["first_name", "last_name", "phone_number"]
        for field in user_fields:
            new_value = self.cleaned_data.get(field)
            if new_value and new_value != getattr(user, field):
                setattr(user, field, new_value)

        # Update password if provided
        password1 = self.cleaned_data.get("password1")
        if password1:
            user.set_password(password1)

        if commit:
            user.save()

            # Update business name
            business_name = self.cleaned_data.get("business_name")
            if business_name:
                profile, _ = ProducerProfile.objects.get_or_create(user=user)
                profile.business_name = business_name
                profile.save()

        return user