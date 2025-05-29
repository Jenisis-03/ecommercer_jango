from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.core.validators import MinValueValidator, MinLengthValidator, RegexValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.conf import settings
import re
from django.db.models.signals import post_save
from django.dispatch import receiver

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
        validators=[MinValueValidator(0)],
        help_text="Base price of the product"
    )
    weight = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Weight of the product"
    )
    length = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Length of the product"
    )
    width = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Width of the product"
    )
    height = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Height of the product"
    )
    meta_title = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="SEO Meta Title"
    )
    meta_description = models.TextField(
        null=True, blank=True,
        help_text="SEO Meta Description"
    )
    meta_keywords = models.CharField(
        max_length=255, null=True, blank=True,
        help_text="SEO Meta Keywords (comma-separated)"
    )
    is_featured = models.BooleanField(default=False)
    is_bestseller = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_special_offer = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)
    is_clearance = models.BooleanField(default=False)
    is_gift = models.BooleanField(default=False)
    is_customizable = models.BooleanField(default=False)
    is_digital = models.BooleanField(default=False)
    is_physical = models.BooleanField(default=True) # Assuming physical by default
    is_subscription = models.BooleanField(default=False)
    is_bundle = models.BooleanField(default=False)
    is_service = models.BooleanField(default=False)
    is_rental = models.BooleanField(default=False)
    is_auction = models.BooleanField(default=False)
    is_pre_order = models.BooleanField(default=False)
    is_back_order = models.BooleanField(default=False)
    is_out_of_stock = models.BooleanField(default=False)
    is_discontinued = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_draft = models.BooleanField(default=False)
    is_pending = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    product_status = models.CharField(
        max_length=20,
        choices=PRODUCT_STATUS_CHOICES,
        default='draft'
    )
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
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    compare_at_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Optional price to show a sale (e.g., original price)"
    )
    cost_per_item = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Cost for internal profit tracking (not shown to customers)"
    )
    requires_shipping = models.BooleanField(default=True)
    stock_keeping_unit = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        help_text="Unique identifier for the product"
    )
    # Tags field (ManyToMany relationship)
    tags = models.ManyToManyField('Tag', blank=True)
    # Collections field (ForeignKey or ManyToMany - assuming ManyToMany for now, need a Collection model)
    # collections = models.ManyToManyField('Collection', blank=True) # Add this line if you create a Collection model

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
    # Add shipping fields as optional
    shipping_address = models.TextField(null=True, blank=True)
    shipping_city = models.CharField(max_length=100, null=True, blank=True)
    shipping_state = models.CharField(max_length=100, null=True, blank=True)
    shipping_zip_code = models.CharField(max_length=20, null=True, blank=True)
    shipping_phone = models.CharField(max_length=20, validators=[validate_phone_number], null=True, blank=True)
    shipping_email = models.EmailField(null=True, blank=True)
    shipping_first_name = models.CharField(max_length=100, null=True, blank=True)
    shipping_last_name = models.CharField(max_length=100, null=True, blank=True)
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
    variant = models.ForeignKey('ProductVariant', on_delete=models.CASCADE, null=True, blank=True)
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

    @property
    def total_amount(self):
        return sum(item.price_at_time * item.quantity for item in self.cartitem_set.all())

    def __str__(self):
        return f"Cart for {self.user.email}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey('ProductVariant', on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.quantity} x {self.product.product_name} in {self.cart.user.email}'s cart"

    @property
    def total_price(self):
        return self.price_at_time * self.quantity

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
    allow_backorders = models.BooleanField(
        default=False,
        help_text="Allow orders to be placed even if this variant is out of stock"
    )

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

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    order_updates = models.BooleanField(default=True)
    promotions = models.BooleanField(default=True)
    newsletter = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_addresses')
    full_name = models.CharField(max_length=100, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=20, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name}'s Address" if self.full_name else "Address"

    class Meta:
        verbose_name_plural = "Addresses"

class PaymentMethod(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    brand = models.CharField(max_length=50)
    last4 = models.CharField(max_length=4)
    exp_month = models.IntegerField()
    exp_year = models.IntegerField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.brand} ending in {self.last4}"

    class Meta:
        ordering = ['-created_at']

class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tags'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class ProductFile(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='product_files/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)
    file_size = models.IntegerField()  # Size in bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.file_name} - {self.product.product_name}"

    def save(self, *args, **kwargs):
        if not self.file_name and self.file:
            self.file_name = self.file.name
        if not self.file_type and self.file:
            self.file_type = self.file.name.split('.')[-1].lower()
        if not self.file_size and self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-uploaded_at']