from django.db import models
from users.models import User
from products.models import Product

class OrderItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE)
    vendor_paid = models.BooleanField(default=False)
    commission_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.quantity} x {self.product.title}"

    def save(self, *args, **kwargs):
        if not self.vendor_id:
            self.vendor = self.product.vendor
        if not self.commission_fee:
            self.commission_fee = self.price * self.quantity * 0.10  # 10% commission
        super().save(*args, **kwargs)

class Order(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled')
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    items = models.ManyToManyField(OrderItem)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_address = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    ordered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Order {self.id} by {self.user.name}"

    def get_vendor_items(self, vendor):
        return self.items.filter(vendor=vendor)

    def get_vendor_total(self, vendor):
        vendor_items = self.get_vendor_items(vendor)
        return sum(item.price * item.quantity for item in vendor_items)