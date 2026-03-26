from django import forms
from mainApp.models import RegularUser
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from mainApp.models import CustomerProfile, Address
from mainApp.utils import geocode_postcode

User = get_user_model()


class CustomerLoginForm(AuthenticationForm):
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
        if user.role != User.Role.CUSTOMER:
            raise ValidationError(
                "This account is not registered as a Customer.",
                code='invalid_role',
            )
        
        # Also check if producer profile exists
        if not hasattr(user, 'customer_profile'):
            raise ValidationError(
                "Your producer profile is not set up correctly. Please contact support.",
                code='no_profile',
            )
        
        super().confirm_login_allowed(user)

class CustomerRegistrationForm(UserCreationForm):
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
    phone_number = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your phone number'
        })
    )

    address_line1 = forms.CharField(
        required=True,
        label="Address Line 1",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Street address, P.O. Box'
        })
    )

    address_line2 = forms.CharField(
        required=False,
        label="Address Line 2 (optional)",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Apartment, suite, unit, etc.'
        })
    )
    
    city = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'City'
        })
    )
    
    county = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'County (optional)'
        })
    )
    
    post_code = forms.CharField(
        required=True,
        label="Post Code",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your post code'
        })
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 
            'password1', 'password2', 'phone_number', 
            'address_line1', 'address_line2', 'city', 'county', 'post_code'
        ]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email, role=User.Role.CUSTOMER).exists():
            raise ValidationError("This email address is already registered as a customer. Please use a different email or login.")
        
        return email
    
    def clean_post_code(self):
        """Validate postcode format"""
        post_code = self.cleaned_data.get('post_code')
        # Basic UK postcode validation
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
        user.role = User.Role.CUSTOMER
        
        if commit:
            user.save()
            CustomerProfile.objects.create(
                user=user,
            )

        lat, lon = geocode_postcode(self.cleaned_data['post_code'])
        
        Address.objects.create(
                user=user,
                address_line1=self.cleaned_data['address_line1'],
                address_line2=self.cleaned_data.get('address_line2', ''),
                city=self.cleaned_data['city'],
                county=self.cleaned_data.get('county', ''),
                post_code=self.cleaned_data['post_code'],
                country='UK',
                address_type='home',
                is_default=True,
                latitude=lat,
                longitude=lon,
            )

        return user
    

class CustomerPersonalInfoForm(forms.ModelForm):
    """
    Form for editing customer personal info, delivery address, and password.
    All fields optional so user can change only what they want.
    """

    # Delivery address fields (home)
    home_address_line1 = forms.CharField(required=False, label="Address Line 1")
    home_address_line2 = forms.CharField(required=False, label="Address Line 2 (optional)")
    home_city = forms.CharField(required=False, label="City")
    home_county = forms.CharField(required=False, label="County (optional)")
    home_post_code = forms.CharField(required=False, label="Post Code")

    # Password
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(),
        label="New Password",
        help_text="Leave blank to keep your current password."
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

        # Make all fields optional
        for field in self.fields.values():
            field.required = False

        # Load home address (default)
        home = self.user.addresses.filter(address_type="home", is_default=True).first()

        if home:
            self.fields["home_address_line1"].initial = home.address_line1
            self.fields["home_address_line2"].initial = home.address_line2
            self.fields["home_city"].initial = home.city
            self.fields["home_county"].initial = home.county
            self.fields["home_post_code"].initial = home.post_code

    def save(self, commit=True):
        user = self.user  # always update existing user

        # Update user fields
        for field in ["username", "email", "first_name", "last_name", "phone_number"]:
            if field in self.cleaned_data:
                new_value = self.cleaned_data[field]
                if new_value != "" and new_value != getattr(user, field):
                    setattr(user, field, new_value)

        # Update password if provided
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)

        if commit:
            user.save()

            # Ensure customer profile exists
            CustomerProfile.objects.get_or_create(user=user)

            # Ensure home address exists
            home = user.addresses.filter(address_type="home", is_default=True).first()
            if not home:
                home = Address.objects.create(
                    user=user,
                    address_line1="",
                    city="",
                    post_code="",
                    country="UK",
                    address_type="home",
                    is_default=True,
                )

            mapping = {
                "home_address_line1": "address_line1",
                "home_address_line2": "address_line2",
                "home_city": "city",
                "home_county": "county",
                "home_post_code": "post_code",
            }

            postcode_changed = False

            for form_field, model_field in mapping.items():
                if form_field in self.cleaned_data:
                    new_value = self.cleaned_data[form_field]
                    if new_value != "" and new_value != getattr(home, model_field):
                        setattr(home, model_field, new_value)
                        if form_field == "home_post_code":
                            postcode_changed = True

            # Re-geocode if postcode changed
            if postcode_changed and home.post_code:
                lat, lon = geocode_postcode(home.post_code)
                home.latitude = lat
                home.longitude = lon

            home.save()

        return user


# class CustomerRegistrationForm(forms.ModelForm):
#     password = forms.CharField(widget=forms.PasswordInput)

#     class Meta:
#         model = RegularUser
#         fields = ["username", "email", "password", "phone_number", "address", "post_code"]