from django.core.management.base import BaseCommand
from accounts.models import Category, Subcategory

class Command(BaseCommand):
    help = 'Seeds the database with default categories and subcategories'

    def handle(self, *args, **kwargs):
        # Clear existing categories and subcategories
        Category.objects.all().delete()
        Subcategory.objects.all().delete()

        # Define categories and their subcategories
        categories_data = {
            'Electronics': ['Smartphones', 'Laptops', 'Headphones', 'Chargers & Cables'],
            'Fashion': ['Men\'s T-Shirts', 'Women\'s Tops', 'Jeans & Trousers', 'Footwear', 'Watches & Accessories'],
            'Home & Kitchen': ['Bedsheets & Towels', 'Cookware', 'Lighting', 'Storage & Organization'],
            'Beauty & Personal Care': ['Skincare Essentials', 'Haircare Products', 'Makeup Kits', 'Fragrances'],
            'Health & Wellness': ['Vitamins & Supplements', 'Yoga Mats', 'Home Medical Devices'],
            'Toys & Games': ['Educational Toys', 'Puzzles & Board Games'],
            'Books': ['Bestsellers', 'Children\'s Books', 'Self-Help & Motivation'],
            'Sports & Outdoors': ['Sports Shoes', 'Fitness Accessories', 'Outdoor Gear'],
            'Grocery': ['Snacks & Beverages', 'Cooking Essentials', 'Breakfast Items'],
            'Pet Supplies': ['Pet Food', 'Pet Accessories']
        }

        # Create categories and their subcategories
        for category_name, subcategories in categories_data.items():
            category = Category.objects.create(category_name=category_name)
            for subcategory_name in subcategories:
                Subcategory.objects.create(
                    category=category,
                    subcategory_name=subcategory_name
                )

        self.stdout.write(self.style.SUCCESS('Successfully seeded categories and subcategories')) 