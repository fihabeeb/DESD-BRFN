from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from mainApp.models import ProducerProfile, Address, RestaurantProfile
from mainApp.utils import geocode_postcode
from django.db import transaction


User = get_user_model()

class ProducerLoginForm(AuthenticationForm):
    """
    Custom login form for producers that checks user role
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your password'
        })
    )

    def confirm_login_allowed(self, user):
        """
        Ensure only users with producer role can login
        """
        if user.role != User.Role.PRODUCER:
            raise ValidationError(
                "This account is not registered as a producer. Please use the customer login.",
                code='invalid_role',
            )
        
        # Also check if producer profile exists
        if not hasattr(user, 'producer_profile'):
            raise ValidationError(
                "Your producer profile is not set up correctly. Please contact support.",
                code='no_profile',
            )
        
        super().confirm_login_allowed(user)


class ProducerRegistrationForm(UserCreationForm):
    """
    Form for producers to register
    """
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your email'
        })
    )
    
    first_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your first name'
        })
    )
    
    last_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your last name'
        })
    )
    
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Choose a username'
        })
    )
    
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Create a password'
        })
    )
    
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Confirm your password'
        })
    )
    
    # Producer specific fields
    business_name = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your farm/business name'
        })
    )
    
    phone_number = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your phone number'
        })
    )

    # Farm address fields (stored in Address model with type='farm')
    farm_address_line1 = forms.CharField(
        required=True,
        label="Farm Address Line 1",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Street address'
        })
    )
    
    farm_address_line2 = forms.CharField(
        required=False,
        label="Farm Address Line 2 (optional)",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Apartment, suite, unit, etc.'
        })
    )
    
    farm_city = forms.CharField(
        required=True,
        label="City/Town",
        initial='Bristol',
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'City'
        })
    )
    
    farm_county = forms.CharField(
        required=False,
        label="County",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'County (optional)'
        })
    )
    
    farm_post_code = forms.CharField(
        required=True,
        label="Farm Post Code",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter farm post code'
        })
    )

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 
            'password1', 'password2', 'phone_number', 'business_name',
            'farm_address_line1', 'farm_address_line2', 'farm_city',
            'farm_county', 'farm_post_code'
        ]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email, role=User.Role.PRODUCER).exists():
            raise ValidationError("This email address is already registered as a producer. Please use a different email or login.")
        
        return email
    
    def clean_farm_post_code(self):
        """Validate farm postcode format"""
        post_code = self.cleaned_data.get('farm_post_code')
        import re
        uk_postcode_pattern = r'^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$'
        if not re.match(uk_postcode_pattern, post_code.upper()):
            raise ValidationError("Please enter a valid UK postcode.")
        return post_code.upper()

    def save(self, commit=True):
        try:
            with transaction.atomic():
                user = super().save(commit=False)
                user.email = self.cleaned_data['email']
                user.first_name = self.cleaned_data['first_name']
                user.last_name = self.cleaned_data['last_name']
                user.phone_number = self.cleaned_data['phone_number']
                user.role = User.Role.PRODUCER
                
                # if commit:
                user.save()
                    # # Geocode postcode for food miles (TC-013)
                    # lat, lon = geocode_postcode(user.post_code)
                    # ProducerProfile.objects.create(
                    #     user=user,
                    #     business_name=self.cleaned_data['business_name'],
                    #     latitude=lat,
                    #     longitude=lon,
                    # )
                lat, lon = geocode_postcode(user.post_code)

                    # Create farm address (for producer location)
                Address.objects.create(
                    user=user,
                    address_line1=self.cleaned_data['farm_address_line1'],
                    address_line2=self.cleaned_data.get('farm_address_line2', ''),
                    city=self.cleaned_data['farm_city'],
                    county=self.cleaned_data.get('farm_county', ''),
                    post_code=self.cleaned_data['farm_post_code'],
                    country='UK',
                    address_type='farm',
                    is_default=True,  # Farm is default for producers
                    latitude=lat,
                    longitude=lon,
                )

                return user
            
        except Exception as e:
            raise e
    


class RestaurantRegistrationForm(UserCreationForm):
    """TC-018: Registration form for restaurant / business accounts."""

    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone_number = forms.CharField(required=True)
    business_name = forms.CharField(required=True, label="Restaurant / Business Name")
    business_registration_number = forms.CharField(
        required=False,
        label="VAT / Company Registration Number (optional)"
    )

    address_line1 = forms.CharField(required=True, label="Address Line 1")
    address_line2 = forms.CharField(required=False, label="Address Line 2 (optional)")
    city = forms.CharField(required=True, initial='Bristol')
    county = forms.CharField(required=False)
    post_code = forms.CharField(required=True, label="Post Code")

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'password1', 'password2', 'phone_number',
            'business_name', 'business_registration_number',
            'address_line1', 'address_line2', 'city', 'county', 'post_code'
        ]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def clean_post_code(self):
        import re
        post_code = self.cleaned_data.get('post_code')
        if not re.match(r'^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$', post_code.upper()):
            raise ValidationError("Please enter a valid UK postcode.")
        return post_code.upper()

    def save(self, commit=True):
        with transaction.atomic():
            user = super().save(commit=False)
            user.email = self.cleaned_data['email']
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.phone_number = self.cleaned_data['phone_number']
            user.role = User.Role.RESTAURANT
            user.save()

            # Update restaurant profile created by signal
            profile = user.restaurant_profile
            profile.business_name = self.cleaned_data['business_name']
            profile.business_registration_number = self.cleaned_data.get('business_registration_number', '')
            profile.save()

            lat, lon = geocode_postcode(self.cleaned_data['post_code'])
            Address.objects.create(
                user=user,
                address_line1=self.cleaned_data['address_line1'],
                address_line2=self.cleaned_data.get('address_line2', ''),
                city=self.cleaned_data['city'],
                county=self.cleaned_data.get('county', ''),
                post_code=self.cleaned_data['post_code'],
                country='UK',
                address_type='business',
                is_default=True,
                latitude=lat,
                longitude=lon,
            )
            return user


class RestaurantLoginForm(AuthenticationForm):
    """Login form for restaurant accounts."""

    def confirm_login_allowed(self, user):
        if user.role != User.Role.RESTAURANT:
            raise ValidationError(
                "This account is not registered as a restaurant.",
                code='invalid_role',
            )
        super().confirm_login_allowed(user)


from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.core.validators import RegexValidator
from mainApp.models import RegularUser, ProducerProfile

class ProducerPersonalInfoForm(forms.Form):
    """Form for producers to update their personal and business information"""
    
    # Personal info fields
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    phone_number = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+1234567890'
        })
    )
    
    # Business info fields
    business_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your farm/business name'
        })
    )

    lead_time_hours = forms.IntegerField(
        min_value=48,
        max_value=168,
        required=False,  # Changed to False since it might not exist for new profiles
        help_text="Minimum hours notice required before delivery (48-168 hours)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 72'
        })
    )
    
    # Password fields
    password1 = forms.CharField(
        label="New Password",
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password (leave blank to keep current)'
        }),
        help_text="Leave blank to keep current password"
    )
    password2 = forms.CharField(
        label="Confirm New Password",
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set initial values from user and profile
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['phone_number'].initial = self.user.phone_number
            
            # Get producer profile
            try:
                profile = ProducerProfile.objects.get(user=self.user)
                self.fields['business_name'].initial = profile.business_name
                # FIXED: Add lead_time_hours initial value
                if hasattr(profile, 'lead_time_hours'):
                    self.fields['lead_time_hours'].initial = profile.lead_time_hours
                else:
                    self.fields['lead_time_hours'].initial = 48  # Default value
            except ProducerProfile.DoesNotExist:
                self.fields['business_name'].initial = ''
                self.fields['lead_time_hours'].initial = 48
    
    def clean_password2(self):
        """Validate that password1 and password2 match"""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 or password2:
            if password1 != password2:
                raise forms.ValidationError("Passwords do not match")
            if len(password1) < 8:
                raise forms.ValidationError("Password must be at least 8 characters long")
        return password2
    
    def clean_lead_time_hours(self):
        lead_time = self.cleaned_data.get('lead_time_hours')
        if lead_time:
            if lead_time < 48:
                raise forms.ValidationError("Lead time must be at least 48 hours (2 days)")
            if lead_time > 168:
                raise forms.ValidationError("Lead time cannot exceed 168 hours (1 week)")
        return lead_time
    
    def save(self):
        """Save the updated user and profile information"""
        if not self.user:
            raise ValueError("User not provided")
        
        # Update user personal info
        self.user.first_name = self.cleaned_data['first_name']
        self.user.last_name = self.cleaned_data['last_name']
        self.user.phone_number = self.cleaned_data['phone_number']
        
        # Update password if provided
        password = self.cleaned_data.get('password1')
        if password:
            self.user.set_password(password)
        
        self.user.save()
        
        # Update or create producer profile
        try:
            profile = ProducerProfile.objects.get(user=self.user)
            profile.business_name = self.cleaned_data['business_name']
            # FIXED: Save lead_time_hours
            lead_time = self.cleaned_data.get('lead_time_hours')
            if lead_time:
                profile.lead_time_hours = lead_time
            profile.save()
        except ProducerProfile.DoesNotExist:
            profile = ProducerProfile.objects.create(
                user=self.user,
                business_name=self.cleaned_data['business_name'],
                lead_time_hours=self.cleaned_data.get('lead_time_hours', 48)  # FIXED: Add lead_time_hours
            )
        
        return self.user