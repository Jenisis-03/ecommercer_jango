from django.core.management.base import BaseCommand
from accounts.models import Vendor, Category, Subcategory, Product, ProductPrice
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Adds dummy data to the database'

    def handle(self, *args, **kwargs):
        # Create a vendor
        vendor = Vendor.objects.create(
            business_name='Tech Store',
            contact_email='tech@store.com',
            password_hash='dummy_hash'
        )

        # Create categories
        electronics = Category.objects.create(
            category_name='Electronics',
            description='Electronic devices and accessories'
        )
        clothing = Category.objects.create(
            category_name='Clothing',
            description='Fashion and apparel'
        )

        # Create subcategories
        phones = Subcategory.objects.create(
            category=electronics,
            subcategory_name='Smartphones'
        )
        laptops = Subcategory.objects.create(
            category=electronics,
            subcategory_name='Laptops'
        )
        tshirts = Subcategory.objects.create(
            category=clothing,
            subcategory_name='T-Shirts'
        )

        # Create products
        products_data = [
            {
                'name': 'iPhone 13',
                'description': 'Latest iPhone model',
                'subcategory': phones,
                'price': 999.99,
                'stock': 50,
                'image_url': 'https://example.com/iphone13.jpg'
            },
            {
                'name': 'MacBook Pro',
                'description': 'Powerful laptop for professionals',
                'subcategory': laptops,
                'price': 1299.99,
                'stock': 30,
                'image_url': 'https://example.com/macbook.jpg'
            },
            {
                'name': 'Cotton T-Shirt',
                'description': 'Comfortable cotton t-shirt',
                'subcategory': tshirts,
                'price': 19.99,
                'stock': 100,
                'image_url': 'https://example.com/tshirt.jpg'
            }
        ]

        for product_data in products_data:
            product = Product.objects.create(
                vendor=vendor,
                subcategory=product_data['subcategory'],
                product_name=product_data['name'],
                description=product_data['description'],
                image_url=product_data['image_url']
            )
            
            ProductPrice.objects.create(
                product=product,
                price=product_data['price'],
                stock_quantity=product_data['stock']
            )

        self.stdout.write(self.style.SUCCESS('Successfully added dummy data'))