import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.core.files import File
from django.utils.text import slugify
from vendors.models import Vendor
from products.models import Category, Product
from decimal import Decimal
import random

User = get_user_model()

# Create main categories
main_categories = [
    'Electronics',
    'Fashion',
    'Home & Living',
    'Books',
    'Sports & Outdoors'
]

# Create subcategories
subcategories = {
    'Electronics': ['Smartphones', 'Laptops', 'Accessories', 'Cameras', 'Audio'],
    'Fashion': ['Men\'s Clothing', 'Women\'s Clothing', 'Kids\'s Clothing', 'Shoes', 'Accessories'],
    'Home & Living': ['Furniture', 'Kitchen', 'Decor', 'Bedding', 'Lighting'],
    'Books': ['Fiction', 'Non-Fiction', 'Academic', 'Children\'s Books', 'Comics'],
    'Sports & Outdoors': ['Exercise Equipment', 'Sports Gear', 'Camping', 'Cycling', 'Swimming']
}

# Create vendor data
vendors_data = [
    {
        'name': 'John Smith',
        'email': 'john@techstore.com',
        'password': 'vendor123',
        'shop_name': 'Tech Store Pro',
        'business_email': 'sales@techstore.com',
        'business_phone': '(555) 123-4567',
        'business_address': '123 Tech Street, Silicon Valley, CA 94025',
        'store_description': 'Your one-stop shop for all things technology',
        'tax_id': 'TSP123456789'
    },
    {
        'name': 'Sarah Johnson',
        'email': 'sarah@fashionista.com',
        'password': 'vendor123',
        'shop_name': 'Fashionista Boutique',
        'business_email': 'sarah@fashionista.com',
        'business_phone': '(555) 234-5678',
        'business_address': '456 Fashion Ave, New York, NY 10018',
        'store_description': 'Trendy fashion for the modern individual',
        'tax_id': 'FB987654321'
    },
    {
        'name': 'Mike Wilson',
        'email': 'mike@homestyle.com',
        'password': 'vendor123',
        'shop_name': 'HomeStyle Living',
        'business_email': 'sales@homestyle.com',
        'business_phone': '(555) 345-6789',
        'business_address': '789 Home Decor Blvd, Los Angeles, CA 90012',
        'store_description': 'Transform your living space with our curated collection',
        'tax_id': 'HL456789123'
    }
]

# Sample products data (title, description, price range)
product_templates = {
    'Smartphones': [
        ('Premium Smartphone', 'High-end smartphone with advanced features', (699, 1299)),
        ('Budget Smartphone', 'Affordable smartphone with essential features', (199, 399))
    ],
    'Laptops': [
        ('Gaming Laptop', 'Powerful laptop for gaming enthusiasts', (999, 1999)),
        ('Business Laptop', 'Reliable laptop for professional use', (599, 1299))
    ],
    'Men\'s Clothing': [
        ('Classic T-Shirt', 'Comfortable cotton t-shirt for everyday wear', (19, 39)),
        ('Formal Shirt', 'Professional button-up shirt', (49, 89))
    ],
    'Women\'s Clothing': [
        ('Summer Dress', 'Light and stylish summer dress', (39, 79)),
        ('Designer Jeans', 'Premium quality designer jeans', (79, 149))
    ],
    'Furniture': [
        ('Modern Sofa', 'Contemporary sofa for your living room', (599, 1499)),
        ('Office Desk', 'Ergonomic desk for home office', (199, 499))
    ]
}

def create_categories():
    created_categories = {}
    for main_cat in main_categories:
        # Check if category already exists
        parent_category, created = Category.objects.get_or_create(
            name=main_cat,
            defaults={'slug': slugify(main_cat)}
        )
        created_categories[main_cat] = {
            'parent': parent_category,
            'subcategories': []
        }
        
        for sub_cat in subcategories[main_cat]:
            # Check if subcategory already exists
            child_category, created = Category.objects.get_or_create(
                name=sub_cat,
                defaults={
                    'slug': slugify(sub_cat),
                    'parent': parent_category
                }
            )
            if not created and not child_category.parent:
                child_category.parent = parent_category
                child_category.save()
            created_categories[main_cat]['subcategories'].append(child_category)
    
    return created_categories

def create_vendors():
    created_vendors = []
    for vendor_data in vendors_data:
        # Create user first
        user = User.objects.create_user(
            email=vendor_data['email'],
            password=vendor_data['password'],
            name=vendor_data['name']
        )
        
        # Set is_vendor flag after creation
        user.is_vendor = True
        user.save()
        
        # Create vendor profile
        vendor = Vendor.objects.create(
            user=user,
            shop_name=vendor_data['shop_name'],
            business_email=vendor_data['business_email'],
            business_phone=vendor_data['business_phone'],
            business_address=vendor_data['business_address'],
            store_description=vendor_data['store_description'],
            tax_id=vendor_data['tax_id']
        )
        created_vendors.append(vendor)
    
    return created_vendors

def create_products(categories, vendors):
    for category_name, templates in product_templates.items():
        # Find the category object
        category = None
        for cat_data in categories.values():
            for subcat in cat_data['subcategories']:
                if subcat.name == category_name:
                    category = subcat
                    break
            if category:
                break
        
        if not category:
            continue
        
        # Create products for this category
        for template in templates:
            title, description, price_range = template
            # Create multiple variations of the product for different vendors
            for vendor in vendors:
                price = Decimal(str(random.uniform(price_range[0], price_range[1])).rstrip('0'))
                quantity = random.randint(10, 100)
                
                Product.objects.create(
                    vendor=vendor,
                    category=category,
                    title=f"{vendor.shop_name} - {title}",
                    description=description,
                    price=price,
                    quantity=quantity,
                    is_active=True
                )

def main():
    print("Creating categories...")
    categories = create_categories()
    
    print("Creating vendors...")
    vendors = create_vendors()
    
    print("Creating products...")
    create_products(categories, vendors)
    
    print("Dummy data creation completed!")

if __name__ == '__main__':
    main()