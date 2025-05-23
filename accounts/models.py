from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinLengthValidator, FileExtensionValidator, MinValueValidator  # Add MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Custom User Model
class CustomUser(AbstractUser):
    username = None  # Disable username field
    email = models.EmailField(unique=True)
    otp = models.CharField(max_length=6, null=True, blank=True, editable=False)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    otp_verified = models.BooleanField(default=False)  # Indicates if OTP was verified
    shop_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        validators=[MinLengthValidator(3)]
    )
    shop_address = models.TextField(
        blank=True,
        null=True,
        validators=[MinLengthValidator(10)]
    )
    is_vendor = models.BooleanField(default=False)  # Whether this user is a vendor

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # No additional fields required during registration

    def __str__(self):
        return self.email


# File Size Validator Function
def validate_file_size(value):
    filesize = value.size
    if filesize > 5 * 1024 * 1024:  # Max size: 5MB
        raise ValidationError(_("The maximum file size that can be uploaded is 5MB"))


# Product Model
class Product(models.Model):
    vendor = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='products'
    )
    name = models.CharField(max_length=200)
    description = models.TextField(max_length=1000)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    image = models.ImageField(
        upload_to='products/',
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(['jpg', 'jpeg', 'png']),
            validate_file_size
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name