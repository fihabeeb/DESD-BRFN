from django import forms
from mainApp.models import RegularUser
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from mainApp.models import CustomerProfile

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
    
    address = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your address'
        })
    )
    
    post_code = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent',
            'placeholder': 'Enter your post code'
        })
    )

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name', 
            'password1', 'password2', 'phone_number', 'address', 'post_code'
        ]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email, role=User.Role.CUSTOMER).exists():
            raise ValidationError("This email address is already registered as a customer. Please use a different email or login.")
        
        return email
    

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        user.address = self.cleaned_data['address']
        user.post_code = self.cleaned_data['post_code']
        user.role = User.Role.CUSTOMER
        
        if commit:
            user.save()
            CustomerProfile.objects.create(
                user=user,
                shipping_address=None,
            )
        
        return user

# class CustomerRegistrationForm(forms.ModelForm):
#     password = forms.CharField(widget=forms.PasswordInput)

#     class Meta:
#         model = RegularUser
#         fields = ["username", "email", "password", "phone_number", "address", "post_code"]