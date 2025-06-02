from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from users.models import User  # Change this import to use the correct User model

class VendorSignUpForm(UserCreationForm):  # Rename to VendorSignUpForm
    name = forms.CharField(max_length=100)
    phone = forms.CharField(max_length=15)
    address = forms.CharField(widget=forms.Textarea)
    shop_name = forms.CharField(max_length=100)  # Add shop_name field

    class Meta:
        model = User
        fields = ['name', 'email', 'phone', 'address', 'shop_name', 'password1', 'password2']


class VendorLoginForm(AuthenticationForm):
    class Meta:
        model = User
        fields = ['email', 'password']