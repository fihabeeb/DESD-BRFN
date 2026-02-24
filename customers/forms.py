from django import forms
from .models import CustomerAddress, Review


class CustomerAddressForm(forms.ModelForm):
    class Meta:
        model = CustomerAddress
        fields = ["line1", "line2", "city", "postcode", "is_default"]


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "title", "body", "is_anonymous"]
        widgets = {
            "rating": forms.RadioSelect(),
            "body": forms.Textarea(attrs={"rows": 4}),
        }