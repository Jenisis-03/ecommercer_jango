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
            'Electronics': {
                'description': 'Electronic devices and accessories',
                'subcategories': {
                    'Mobile Phones': ['Smartphones', 'Feature Phones', 'Phone Accessories'],
                    'Laptops & Computers': ['Laptops', 'Desktops', 'Monitors', 'Keyboards & Mice'],
                    'TVs & Home Entertainment': ['LED TVs', 'Home Theaters', 'Streaming Devices'],
                    'Cameras & Drones': ['DSLR Cameras', 'Action Cameras', 'Drones']
                }
            },
            'Fashion': {
                'description': 'Clothing and fashion accessories',
                'subcategories': {
                    'Men': ['T-Shirts', 'Jeans', 'Shoes', 'Watches'],
                    'Women': ['Dresses', 'Sarees', 'Footwear', 'Jewelry'],
                    'Accessories': ['Bags', 'Belts', 'Sunglasses', 'Hats']
                }
            },
            'Home & Kitchen': {
                'description': 'Home decor and kitchen essentials',
                'subcategories': {
                    'Furniture': ['Sofas', 'Beds', 'Tables', 'Chairs'],
                    'Kitchenware': ['Cookware', 'Cutlery', 'Small Appliances'],
                    'Home Decor': ['Wall Art', 'Lighting', 'Curtains']
                }
            },
            'Beauty & Personal Care': {
                'description': 'Beauty and personal care products',
                'subcategories': {
                    'Skincare': ['Moisturizers', 'Cleansers', 'Face Masks'],
                    'Haircare': ['Shampoos', 'Conditioners', 'Hair Tools'],
                    'Makeup': ['Eyeshadow', 'Foundation', 'Lipstick']
                }
            },
            'Sports & Outdoors': {
                'description': 'Sports equipment and outdoor gear',
                'subcategories': {
                    'Fitness': ['Dumbbells', 'Yoga Mats', 'Exercise Bikes'],
                    'Outdoor Gear': ['Tents', 'Sleeping Bags', 'Hiking Boots'],
                    'Team Sports': ['Football', 'Cricket', 'Basketball']
                }
            },
            'Toys & Games': {
                'description': 'Toys and games for all ages',
                'subcategories': {
                    'Kids Toys': ['Action Figures', 'Building Blocks', 'Dolls'],
                    'Board Games': ['Strategy Games', 'Family Games', 'Card Games'],
                    'Learning & Education': ['STEM Kits', 'Puzzles', 'Art Supplies']
                }
            },
            'Books': {
                'description': 'Books and literature',
                'subcategories': {
                    'Fiction': ['Thrillers', 'Romance', 'Fantasy'],
                    'Non-Fiction': ['Biographies', 'Self-Help', 'History'],
                    'Children\'s Books': ['Picture Books', 'Educational', 'Bedtime Stories']
                }
            },
            'Automotive': {
                'description': 'Automotive parts and accessories',
                'subcategories': {
                    'Car Accessories': ['Seat Covers', 'Air Fresheners', 'Dash Cams'],
                    'Tools & Equipment': ['Jacks', 'Battery Chargers', 'Tool Kits'],
                    'Motorcycle': ['Helmets', 'Gloves', 'Parts']
                }
            }
        }

        # Create categories and their subcategories
        for category_name, category_data in categories_data.items():
            category = Category.objects.create(
                category_name=category_name,
                description=category_data['description']
            )
            self.stdout.write(f'Created category: {category.category_name}')
            
            for subcategory_name, subsubcategories in category_data['subcategories'].items():
                subcategory = Subcategory.objects.create(
                    category=category,
                    subcategory_name=subcategory_name
                )
                self.stdout.write(f'Created subcategory: {subcategory.subcategory_name}')
                
                for subsubcategory_name in subsubcategories:
                    subsubcategory = Subcategory.objects.create(
                        category=category,
                        subcategory_name=subsubcategory_name
                    )
                    self.stdout.write(f'Created subsubcategory: {subsubcategory.subcategory_name}')

        self.stdout.write(self.style.SUCCESS('Successfully seeded categories and subcategories')) 