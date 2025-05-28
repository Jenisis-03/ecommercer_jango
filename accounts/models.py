from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.core.validators import MinValueValidator, MinLengthValidator, RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.conf import settings
import re

# Product status choices
PRODUCT_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
    ('pending', 'Pending Review'),
    ('archived', 'Archived')
]

# Order status choices
ORDER_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('processing', 'Processing'),
    ('shipped', 'Shipped'),
    ('delivered', 'Delivered'),
    ('cancelled', 'Cancelled'),
    ('refunded', 'Refunded')
]

def validate_phone_number(value):
    if value and not re.match(r'^\+?1?\d{9,15}$', value):
        raise ValidationError('Please enter a valid phone number')

def validate_zip_code(value):
    if not re.match(r'^\d{5}(-\d{4})?$', value):
        raise ValidationError('Please enter a valid zip code')

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    email = models.EmailField(unique=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    phone_number = models.CharField(
        max_length=15, 
        blank=True, 
        null=True,
        validators=[validate_phone_number]
    )
    is_verified = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.email

    @property
    def is_vendor(self):
        return hasattr(self, 'vendor')

class Vendor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    business_name = models.CharField(max_length=100, unique=True)
    shop_address = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    email_notifications = models.BooleanField(default=True)
    order_notifications = models.BooleanField(default=True)
    store_status = models.CharField(
        max_length=20,
        choices=(
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('suspended', 'Suspended'),
        ),
        default='active'
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'vendors'
        indexes = [
            models.Index(fields=['business_name']),
            models.Index(fields=['store_status']),
        ]

    def __str__(self):
        return self.business_name

    def save(self, *args, **kwargs):
        if self.user and not self.user.is_active:
            self.user.is_active = True
            self.user.save()
        super().save(*args, **kwargs)

class Category(models.Model):
    category_name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        indexes = [
            models.Index(fields=['category_name']),
        ]

    def __str__(self):
        return self.category_name

class Subcategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    subcategory_name = models.CharField(max_length=100)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'subcategories'
        verbose_name_plural = 'Subcategories'
        unique_together = ('category', 'subcategory_name')
        indexes = [
            models.Index(fields=['category', 'subcategory_name']),
        ]

    def __str__(self):
        return f"{self.category.category_name} - {self.subcategory_name}"

class Product(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    product_name = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(3)]
    )
    product_description = models.TextField(
        validators=[MinLengthValidator(10)]
    )
    subcategory = models.ForeignKey(Subcategory, on_delete=models.CASCADE)
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    product_status = models.CharField(
        max_length=20,
        choices=PRODUCT_STATUS_CHOICES,
        default='draft'
    )
    is_featured = models.BooleanField(default=False)
    product_weight = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    product_length = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    product_width = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    product_height = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)]
    )
    meta_title = models.CharField(max_length=200, null=True, blank=True)
    meta_description = models.TextField(null=True, blank=True)
    meta_keywords = models.CharField(max_length=200, null=True, blank=True)
    canonical_url = models.URLField(null=True, blank=True)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'products'
        indexes = [
            models.Index(fields=['product_name']),
            models.Index(fields=['product_status']),
            models.Index(fields=['vendor', 'product_status']),
            models.Index(fields=['is_featured']),
        ]

    def __str__(self):
        return self.product_name

    def get_current_price(self):
        if self.variants.exists():
            return min(variant.price for variant in self.variants.all())
        return self.base_price

    def get_available_stock(self):
        return sum(variant.stock for variant in self.variants.all())

class ProductPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    stock_quantity = models.IntegerField(
        validators=[MinValueValidator(0)]
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_prices'
        indexes = [
            models.Index(fields=['product', 'updated_at']),
        ]

    def __str__(self):
        return f"{self.product.product_name} - ${self.price}"

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order_date = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    status = models.CharField(
        max_length=50,
        choices=ORDER_STATUS_CHOICES,
        default='pending'
    )
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'orders'
        indexes = [
            models.Index(fields=['user', 'order_date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.user.email}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    price_at_time = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        db_table = 'order_items'
        indexes = [
            models.Index(fields=['order', 'product']),
        ]

    def __str__(self):
        return f"{self.product.product_name} x {self.quantity}"

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'carts'
        indexes = [
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"Cart for {self.user.email}"

    @property
    def total_price(self):
        return sum(item.total_price for item in self.cartitem_set.all())

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    variant = models.ForeignKey('ProductVariant', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = 'cart_items'
        unique_together = ('cart', 'product', 'variant')
        indexes = [
            models.Index(fields=['cart', 'product']),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product.product_name}"

    def clean(self):
        if self.quantity > self.product.get_available_stock():
            raise ValidationError('Not enough stock available')

    @property
    def total_price(self):
        if self.variant:
            return self.variant.price * self.quantity
        current_price = self.product.productprice_set.order_by('-updated_at').first()
        if current_price:
            return current_price.price * self.quantity
        return self.product.base_price * self.quantity

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    color = models.CharField(max_length=50)
    size = models.CharField(max_length=20)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    stock = models.PositiveIntegerField()
    sku = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('product', 'color', 'size')
        indexes = [
            models.Index(fields=['product', 'sku']),
            models.Index(fields=['stock']),
        ]

    def __str__(self):
        return f"{self.product.product_name} - {self.color} - {self.size}"

    def save(self, *args, **kwargs):
        if not self.product.variants.exists():
            self.product.base_price = self.price
            self.product.save()
        super().save(*args, **kwargs)

class Wishlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'wishlists'
        unique_together = ('user', 'product')
        ordering = ['-date_added']
        indexes = [
            models.Index(fields=['user', 'product']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.product.product_name}"

class Address(models.Model):
    ADDRESS_TYPES = (
        ('shipping', 'Shipping Address'),
        ('billing', 'Billing Address'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=20, choices=ADDRESS_TYPES)
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(
        max_length=20,
        validators=[validate_zip_code]
    )
    country = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'addresses'
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'address_type']),
            models.Index(fields=['is_default']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.address_type}"

    def clean(self):
        if self.is_default:
            # Set other addresses of same type to non-default
            Address.objects.filter(
                user=self.user,
                address_type=self.address_type,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)