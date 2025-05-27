from django.core.management.base import BaseCommand
from accounts.models import Vendor, Category, Subcategory, Product, ProductPrice
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from decimal import Decimal
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Adds dummy data to the database'

    def handle(self, *args, **kwargs):
        # Create vendors
        vendors_data = [
            {
                'business_name': 'TechGadgets Pro',
                'contact_email': 'contact@techgadgetspro.com',
                'shop_address': '123 Tech Street, Silicon Valley, CA 94025',
                'first_name': 'John',
                'last_name': 'Tech'
            },
            {
                'business_name': 'Fashion Forward',
                'contact_email': 'info@fashionforward.com',
                'shop_address': '456 Style Avenue, New York, NY 10001',
                'first_name': 'Sarah',
                'last_name': 'Style'
            },
            {
                'business_name': 'Home Essentials',
                'contact_email': 'support@homeessentials.com',
                'shop_address': '789 Home Lane, Chicago, IL 60601',
                'first_name': 'Mike',
                'last_name': 'Home'
            }
        ]

        vendors = []
        for vendor_data in vendors_data:
            # Check if user exists
            user, user_created = User.objects.get_or_create(
                email=vendor_data['contact_email'],
                defaults={
                    'first_name': vendor_data['first_name'],
                    'last_name': vendor_data['last_name']
                }
            )
            
            if user_created:
                user.set_password('vendor123')
                user.save()
                self.stdout.write(f'Created user: {user.email}')
            else:
                self.stdout.write(f'Found existing user: {user.email}')
            
            # Check if vendor exists
            vendor, vendor_created = Vendor.objects.get_or_create(
                contact_email=vendor_data['contact_email'],
                defaults={
                    'user': user,
                    'business_name': vendor_data['business_name'],
                    'shop_address': vendor_data['shop_address']
                }
            )
            
            if not vendor_created:
                # Update existing vendor
                vendor.user = user
                vendor.business_name = vendor_data['business_name']
                vendor.shop_address = vendor_data['shop_address']
                vendor.save()
                self.stdout.write(f'Updated vendor: {vendor.business_name}')
            else:
                self.stdout.write(f'Created vendor: {vendor.business_name}')
            
            vendors.append(vendor)

        # Create categories and subcategories
        categories_data = {
            'Electronics': {
                'description': 'Electronic devices and accessories',
                'subcategories': ['Smartphones', 'Laptops', 'Tablets', 'Accessories']
            },
            'Fashion': {
                'description': 'Clothing and fashion accessories',
                'subcategories': ['Men\'s Clothing', 'Women\'s Clothing', 'Footwear', 'Accessories']
            },
            'Home & Living': {
                'description': 'Home decor and essentials',
                'subcategories': ['Furniture', 'Kitchenware', 'Decor', 'Lighting']
            }
        }

        categories = {}
        subcategories = {}
        for cat_name, cat_data in categories_data.items():
            category, cat_created = Category.objects.get_or_create(
                category_name=cat_name,
                defaults={'description': cat_data['description']}
            )
            categories[cat_name] = category
            
            if cat_created:
                self.stdout.write(f'Created category: {category.category_name}')
            else:
                self.stdout.write(f'Found existing category: {category.category_name}')
            
            for subcat_name in cat_data['subcategories']:
                subcategory, subcat_created = Subcategory.objects.get_or_create(
                    category=category,
                    subcategory_name=subcat_name
                )
                subcategories[f"{cat_name}_{subcat_name}"] = subcategory
                
                if subcat_created:
                    self.stdout.write(f'Created subcategory: {subcategory.subcategory_name}')
                else:
                    self.stdout.write(f'Found existing subcategory: {subcategory.subcategory_name}')

        # Create products
        products_data = [
            # Electronics - Smartphones
            {
                'name': 'iPhone 15 Pro',
                'description': 'Latest iPhone with A17 Pro chip, titanium design, and advanced camera system',
                'vendor': vendors[0],
                'subcategory': subcategories['Electronics_Smartphones'],
                'base_price': Decimal('999.99'),
                'current_sale_price': Decimal('949.99'),
                'available_stock': 50,
                'product_weight': Decimal('0.187'),
                'product_length': Decimal('5.77'),
                'product_width': Decimal('2.78'),
                'product_height': Decimal('0.32'),
                'image_url': 'https://example.com/iphone15pro.jpg',
                'meta_title': 'iPhone 15 Pro - Latest Apple Smartphone with A17 Pro Chip',
                'meta_description': 'Experience the future with iPhone 15 Pro. Featuring titanium design, A17 Pro chip, and advanced camera system.',
                'meta_keywords': 'iPhone 15 Pro, Apple, smartphone, A17 Pro, titanium, camera',
                'canonical_url': 'https://example.com/iphone15pro',
                'product_status': 'published',
                'is_featured': True
            },
            {
                'name': 'Samsung Galaxy S24 Ultra',
                'description': 'Premium Android smartphone with S Pen, advanced AI features, and 200MP camera',
                'vendor': vendors[0],
                'subcategory': subcategories['Electronics_Smartphones'],
                'base_price': Decimal('1199.99'),
                'current_sale_price': Decimal('1099.99'),
                'available_stock': 40,
                'product_weight': Decimal('0.233'),
                'product_length': Decimal('6.40'),
                'product_width': Decimal('3.11'),
                'product_height': Decimal('0.34'),
                'image_url': 'https://example.com/s24ultra.jpg',
                'meta_title': 'Samsung Galaxy S24 Ultra - AI-Powered Premium Smartphone',
                'meta_description': 'Discover the Samsung Galaxy S24 Ultra with S Pen, advanced AI features, and revolutionary 200MP camera system.',
                'meta_keywords': 'Samsung, Galaxy S24 Ultra, Android, smartphone, AI, S Pen',
                'canonical_url': 'https://example.com/s24ultra',
                'product_status': 'published',
                'is_featured': True
            },
            # Electronics - Laptops
            {
                'name': 'MacBook Pro M3',
                'description': 'Powerful laptop with M3 chip, Liquid Retina XDR display, and up to 22 hours battery life',
                'vendor': vendors[0],
                'subcategory': subcategories['Electronics_Laptops'],
                'base_price': Decimal('1999.99'),
                'current_sale_price': None,
                'available_stock': 25,
                'product_weight': Decimal('4.7'),
                'product_length': Decimal('14.01'),
                'product_width': Decimal('9.77'),
                'product_height': Decimal('0.61'),
                'image_url': 'https://example.com/macbookpro.jpg',
                'meta_title': 'MacBook Pro M3 - Ultimate Professional Laptop',
                'meta_description': 'Experience unmatched performance with MacBook Pro M3. Featuring Liquid Retina XDR display and 22-hour battery life.',
                'meta_keywords': 'MacBook Pro, M3, laptop, Apple, professional',
                'canonical_url': 'https://example.com/macbookpro-m3',
                'product_status': 'published',
                'is_featured': True
            },
            # Fashion - Men's Clothing
            {
                'name': 'Premium Cotton T-Shirt',
                'description': 'High-quality cotton t-shirt with modern fit and sustainable materials',
                'vendor': vendors[1],
                'subcategory': subcategories['Fashion_Men\'s Clothing'],
                'base_price': Decimal('29.99'),
                'current_sale_price': Decimal('24.99'),
                'available_stock': 100,
                'product_weight': Decimal('0.2'),
                'product_length': Decimal('28'),
                'product_width': Decimal('20'),
                'product_height': Decimal('0.1'),
                'image_url': 'https://example.com/tshirt.jpg',
                'meta_title': 'Premium Cotton T-Shirt - Sustainable Fashion',
                'meta_description': 'Eco-friendly premium cotton t-shirt with modern fit. Perfect for everyday wear.',
                'meta_keywords': 't-shirt, cotton, sustainable, men\'s clothing, casual',
                'canonical_url': 'https://example.com/premium-tshirt',
                'product_status': 'published',
                'is_featured': False
            },
            # Fashion - Women's Clothing
            {
                'name': 'Designer Summer Dress',
                'description': 'Elegant summer dress with floral pattern and comfortable fit',
                'vendor': vendors[1],
                'subcategory': subcategories['Fashion_Women\'s Clothing'],
                'base_price': Decimal('89.99'),
                'current_sale_price': Decimal('69.99'),
                'available_stock': 75,
                'product_weight': Decimal('0.3'),
                'product_length': Decimal('35'),
                'product_width': Decimal('25'),
                'product_height': Decimal('0.2'),
                'image_url': 'https://example.com/dress.jpg',
                'meta_title': 'Designer Summer Dress - Floral Pattern',
                'meta_description': 'Beautiful floral summer dress with elegant design and comfortable fit.',
                'meta_keywords': 'summer dress, floral, women\'s clothing, designer',
                'canonical_url': 'https://example.com/summer-dress',
                'product_status': 'published',
                'is_featured': True
            },
            # Home & Living - Furniture
            {
                'name': 'Modern Sofa Set',
                'description': 'Contemporary 3-seater sofa with matching armchairs, premium fabric',
                'vendor': vendors[2],
                'subcategory': subcategories['Home & Living_Furniture'],
                'base_price': Decimal('1299.99'),
                'current_sale_price': Decimal('1099.99'),
                'available_stock': 15,
                'product_weight': Decimal('85'),
                'product_length': Decimal('220'),
                'product_width': Decimal('90'),
                'product_height': Decimal('85'),
                'image_url': 'https://example.com/sofa.jpg',
                'meta_title': 'Modern Sofa Set - Contemporary Living Room Furniture',
                'meta_description': 'Elegant 3-seater sofa set with matching armchairs. Perfect for modern living spaces.',
                'meta_keywords': 'sofa set, furniture, living room, modern, contemporary',
                'canonical_url': 'https://example.com/modern-sofa-set',
                'product_status': 'published',
                'is_featured': True
            },
            # Home & Living - Kitchenware
            {
                'name': 'Professional Cookware Set',
                'description': '10-piece stainless steel cookware set with non-stick coating',
                'vendor': vendors[2],
                'subcategory': subcategories['Home & Living_Kitchenware'],
                'base_price': Decimal('299.99'),
                'current_sale_price': Decimal('249.99'),
                'available_stock': 30,
                'product_weight': Decimal('12'),
                'product_length': Decimal('40'),
                'product_width': Decimal('30'),
                'product_height': Decimal('25'),
                'image_url': 'https://example.com/cookware.jpg',
                'meta_title': 'Professional Cookware Set - 10-Piece Collection',
                'meta_description': 'Complete 10-piece stainless steel cookware set with non-stick coating. Perfect for professional and home cooking.',
                'meta_keywords': 'cookware, kitchenware, stainless steel, non-stick, cooking set',
                'canonical_url': 'https://example.com/pro-cookware-set',
                'product_status': 'published',
                'is_featured': False
            }
        ]

        for product_data in products_data:
            # Generate SKU
            sku = f"{product_data['vendor'].business_name[:3].upper()}-{product_data['subcategory'].subcategory_name[:3].upper()}-{random.randint(1000, 9999)}"
            
            # Generate slug
            slug = slugify(product_data['name'])
            
            # Check if product exists
            product, product_created = Product.objects.get_or_create(
                stock_keeping_unit=sku,
                defaults={
                    'vendor': product_data['vendor'],
                    'subcategory': product_data['subcategory'],
                    'product_name': product_data['name'],
                    'product_description': product_data['description'],
                    'base_price': product_data['base_price'],
                    'current_sale_price': product_data['current_sale_price'],
                    'available_stock': product_data['available_stock'],
                    'product_weight': product_data['product_weight'],
                    'product_length': product_data['product_length'],
                    'product_width': product_data['product_width'],
                    'product_height': product_data['product_height'],
                    'image_url': product_data['image_url'],
                    'slug': slug,
                    'product_status': product_data['product_status'],
                    'is_featured': product_data['is_featured'],
                    'meta_title': product_data['meta_title'],
                    'meta_description': product_data['meta_description'],
                    'meta_keywords': product_data['meta_keywords'],
                    'canonical_url': product_data['canonical_url']
                }
            )
            
            if not product_created:
                # Update existing product
                product.vendor = product_data['vendor']
                product.subcategory = product_data['subcategory']
                product.product_name = product_data['name']
                product.product_description = product_data['description']
                product.base_price = product_data['base_price']
                product.current_sale_price = product_data['current_sale_price']
                product.available_stock = product_data['available_stock']
                product.product_weight = product_data['product_weight']
                product.product_length = product_data['product_length']
                product.product_width = product_data['product_width']
                product.product_height = product_data['product_height']
                product.image_url = product_data['image_url']
                product.slug = slug
                product.product_status = product_data['product_status']
                product.is_featured = product_data['is_featured']
                product.meta_title = product_data['meta_title']
                product.meta_description = product_data['meta_description']
                product.meta_keywords = product_data['meta_keywords']
                product.canonical_url = product_data['canonical_url']
                product.save()
                self.stdout.write(f'Updated product: {product.product_name}')
            else:
                self.stdout.write(f'Created product: {product.product_name}')
            
            # Create or update product price
            price, price_created = ProductPrice.objects.get_or_create(
                product=product,
                defaults={
                    'price': product_data['current_sale_price'] or product_data['base_price'],
                    'stock_quantity': product_data['available_stock']
                }
            )
            
            if not price_created:
                price.price = product_data['current_sale_price'] or product_data['base_price']
                price.stock_quantity = product_data['available_stock']
                price.save()
                self.stdout.write(f'Updated price for: {product.product_name}')
            else:
                self.stdout.write(f'Created price for: {product.product_name}')

        self.stdout.write(self.style.SUCCESS('Successfully added/updated dummy data'))