from django import forms
from mainApp.models import RegularUser

class CustomerRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = RegularUser
        fields = ["username", "email", "password", "phone_number", "address", "post_code"]