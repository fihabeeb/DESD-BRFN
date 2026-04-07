from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from mainApp.models import ProducerProfile, Address
from mainApp.utils import geocode_postcode

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
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        user.role = User.Role.PRODUCER
        
        if commit:
            user.save()
            # Geocode postcode for food miles (TC-013)
            lat, lon = geocode_postcode(user.post_code)
            ProducerProfile.objects.create(
                user=user,
                business_name=self.cleaned_data['business_name'],
                latitude=lat,
                longitude=lon,
            )

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