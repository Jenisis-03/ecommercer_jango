from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.text import slugify

# Product status choices
PRODUCT_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
    ('pending', 'Pending Review'),
    ('archived', 'Archived')
]

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
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email

class Vendor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    business_name = models.CharField(max_length=100)
    contact_email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    shop_address = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'vendors'

    def __str__(self):
        return self.business_name

class Category(models.Model):
    category_name = models.CharField(max_length=100)
    description = models.TextField()

    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.category_name

class Subcategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    subcategory_name = models.CharField(max_length=100)

    class Meta:
        db_table = 'subcategories'
        verbose_name_plural = 'Subcategories'

    def __str__(self):
        return f"{self.category.category_name} - {self.subcategory_name}"

class Product(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    product_name = models.CharField(max_length=200)
    product_description = models.TextField()
    subcategory = models.ForeignKey(Subcategory, on_delete=models.CASCADE)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    product_status = models.CharField(max_length=20, choices=PRODUCT_STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    product_weight = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    product_length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    product_width = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    product_height = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    meta_title = models.CharField(max_length=200, null=True, blank=True)
    meta_description = models.TextField(null=True, blank=True)
    meta_keywords = models.CharField(max_length=200, null=True, blank=True)
    canonical_url = models.URLField(null=True, blank=True)
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product_name

    def get_current_price(self):
        return self.base_price

    def get_available_stock(self):
        return sum(variant.stock for variant in self.variants.all())

class ProductPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'product_prices'

    def __str__(self):
        return f"{self.product.product_name} - ${self.price}"

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order_date = models.DateTimeField(default=timezone.now)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50)

    class Meta:
        db_table = 'orders'

    def __str__(self):
        return f"Order #{self.id} - {self.user.email}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'order_items'

    def __str__(self):
        return f"{self.product.product_name} x {self.quantity}"

def validate_file_size(value):
    filesize = value.size
    if filesize > 1024 * 1024:  # 1MB
        raise ValidationError("Maximum file size that can be uploaded is 1MB")
    return value

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'carts'

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

    class Meta:
        db_table = 'cart_items'
        unique_together = ('cart', 'product')

    def __str__(self):
        return f"{self.quantity} x {self.product.product_name}"

    @property
    def total_price(self):
        current_price = self.product.productprice_set.order_by('-updated_at').first()
        return current_price.price * self.quantity if current_price else 0

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    color = models.CharField(max_length=50)
    size = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    sku = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'color', 'size')

    def __str__(self):
        return f"{self.product.product_name} - {self.color} - {self.size}"

    def save(self, *args, **kwargs):
        # Update product's base price if this is the first variant
        if not self.product.variants.exists():
            self.product.base_price = self.price
            self.product.save()
        super().save(*args, **kwargs)