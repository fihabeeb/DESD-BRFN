from django import forms
from django.contrib.auth import get_user_model
from mainApp.models import ProducerProfile, Address
from mainApp.utils import geocode_postcode

User = get_user_model()


class ProducerPersonalInfoForm(forms.ModelForm):
    """
    Form for editing producer personal, business, and farm information.
    All fields are optional so the user can update only one field at a time.
    """

    # Business info
    business_name = forms.CharField(required=False)

    # Farm address fields
    farm_address_line1 = forms.CharField(required=False)
    farm_address_line2 = forms.CharField(required=False)
    farm_city = forms.CharField(required=False)
    farm_county = forms.CharField(required=False)
    farm_post_code = forms.CharField(required=False)

    # Password
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(),
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

    def save(self, commit=True):
        """
        IMPORTANT: This must update self.user, not create a new one.
        """
        user = self.user  # always work on the existing logged-in user

        # Update only changed user fields
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

            # Ensure producer profile exists
            profile, _ = ProducerProfile.objects.get_or_create(user=user)

            # Update business name
            if self.cleaned_data.get("business_name"):
                profile.business_name = self.cleaned_data["business_name"]

            # Ensure farm address exists
            farm = user.addresses.filter(address_type="farm", is_default=True).first()
            if not farm:
                farm = Address.objects.create(
                    user=user,
                    address_line1="",
                    city="",
                    post_code="",
                    country="UK",
                    address_type="farm",
                    is_default=True
                )

            mapping = {
                "farm_address_line1": "address_line1",
                "farm_address_line2": "address_line2",
                "farm_city": "city",
                "farm_county": "county",
                "farm_post_code": "post_code",
            }

            postcode_changed = False

            for form_field, model_field in mapping.items():
                if form_field in self.cleaned_data:
                    new_value = self.cleaned_data[form_field]
                    if new_value != "" and new_value != getattr(farm, model_field):
                        setattr(farm, model_field, new_value)
                        if form_field == "farm_post_code":
                            postcode_changed = True

            # Re-geocode if postcode changed
            if postcode_changed and farm.post_code:
                lat, lon = geocode_postcode(farm.post_code)
                profile.latitude = lat
                profile.longitude = lon
                farm.latitude = lat
                farm.longitude = lon

            farm.save()
            profile.save()

        return user
