from django.core.management.base import BaseCommand
from django.core.files import File
from accounts.models import CustomUser, Product
from django.conf import settings
import os
from decimal import Decimal

class Command(BaseCommand):
    help = 'Adds dummy products to the database'

    def handle(self, *args, **kwargs):
        # First, create a vendor if none exists
        vendor, created = CustomUser.objects.get_or_create(
            email='vendor@example.com',
            defaults={
                'is_vendor': True,
                'is_active': True,
            }
        )
        if created:
            vendor.set_password('vendor123')
            vendor.save()

        # Dummy product data
        products = [
            {
                'name': 'Smartphone X',
                'description': 'Latest smartphone with advanced features and 5G capability.',
                'price': Decimal('699.99'),
                'stock': 50,
            },
            {
                'name': 'Laptop Pro',
                'description': 'Professional laptop with high performance and long battery life.',
                'price': Decimal('1299.99'),
                'stock': 30,
            },
            {
                'name': 'Wireless Earbuds',
                'description': 'Premium wireless earbuds with noise cancellation.',
                'price': Decimal('149.99'),
                'stock': 100,
            },
            {
                'name': 'Smart Watch',
                'description': 'Fitness tracking smartwatch with heart rate monitor.',
                'price': Decimal('199.99'),
                'stock': 75,
            },
            {
                'name': 'Gaming Console',
                'description': 'Next-gen gaming console for immersive gaming experience.',
                'price': Decimal('499.99'),
                'stock': 25,
            },
            {
                'name': 'Tablet Ultra',
                'description': 'Lightweight tablet perfect for work and entertainment.',
                'price': Decimal('399.99'),
                'stock': 40,
            },
        ]

        for product_data in products:
            product = Product.objects.create(
                vendor=vendor,
                **product_data
            )
            self.stdout.write(f'Created product: {product.name}')

        self.stdout.write(self.style.SUCCESS('Successfully added dummy products'))