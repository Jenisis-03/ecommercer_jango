from django.db import models
from users.models import User

class Vendor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shop_name = models.CharField(max_length=100)
    business_email = models.EmailField(blank=True)
    business_phone = models.CharField(max_length=20, blank=True)
    business_address = models.TextField(blank=True)
    store_description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='store_logos/', blank=True)
    banner = models.ImageField(upload_to='store_banners/', blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.shop_name

    def get_total_sales(self):
        from orders.models import Order
        return Order.objects.filter(items__product__vendor=self).distinct().count()

    def get_total_revenue(self):
        from orders.models import Order
        orders = Order.objects.filter(items__product__vendor=self).distinct()
        return sum(order.total_price for order in orders)