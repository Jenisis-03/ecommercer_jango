from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Vendor, Category, Subcategory, Product, ProductPrice, Order, OrderItem, ProductVariant, Cart, CartItem, Wishlist, Profile, Address, PaymentMethod, Tag, ProductFile

class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'is_active')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name'),
        }),
        ('Permissions', {
            'fields': ('is_staff', 'is_superuser', 'is_active')
        }),
    )

class VendorAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'created_at')
    search_fields = ('business_name', 'contact_email')
    ordering = ('business_name',)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('category_name', 'description')
    search_fields = ('category_name',)
    ordering = ('category_name',)

class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ('subcategory_name', 'category')
    search_fields = ('subcategory_name', 'category__category_name')
    list_filter = ('category',)
    ordering = ('category', 'subcategory_name')

class ProductPriceInline(admin.TabularInline):
    model = ProductPrice
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'vendor', 'subcategory', 'base_price', 'product_status', 'is_featured', 'created_at')
    list_filter = ('product_status', 'is_featured', 'created_at', 'vendor', 'subcategory')
    search_fields = ('product_name', 'product_description', 'vendor__business_name')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    fieldsets = (
        ('Basic Information', {
            'fields': ('product_name', 'product_description', 'vendor', 'subcategory', 'image')
        }),
        ('Pricing & Status', {
            'fields': ('base_price', 'product_status', 'is_featured')
        }),
        ('Dimensions', {
            'fields': ('product_weight', 'product_length', 'product_width', 'product_height')
        }),
        ('SEO Information', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords', 'canonical_url')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )

@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'color', 'size', 'price', 'stock', 'sku')
    list_filter = ('product', 'color', 'size')
    search_fields = ('product__product_name', 'sku', 'color', 'size')
    readonly_fields = ('created_at', 'updated_at')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price_at_time')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'order_date', 'total_amount', 'status')
    list_filter = ('status', 'order_date')
    search_fields = ('user__email', 'id')
    ordering = ('-order_date',)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price_at_time')
    list_filter = ('order__status',)
    search_fields = ('order__id', 'product__product_name')

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    search_fields = ('user__email',)
    ordering = ('-created_at',)

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'quantity', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('cart__user__email', 'product__product_name')

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'date_added')
    search_fields = ('user__email', 'product__product_name')
    list_filter = ('date_added',)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'order_updates', 'promotions', 'newsletter')
    search_fields = ('user__email', 'phone')

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'city', 'state', 'is_default')
    search_fields = ('user__email', 'full_name', 'city')
    list_filter = ('is_default', 'state')

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('user', 'brand', 'last4', 'exp_month', 'exp_year', 'is_default')
    search_fields = ('user__email', 'last4')
    list_filter = ('brand', 'is_default')

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'created_at')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(ProductFile)
class ProductFileAdmin(admin.ModelAdmin):
    list_display = ('product', 'file_name', 'file_type', 'file_size', 'uploaded_at')
    search_fields = ('product__product_name', 'file_name')
    list_filter = ('file_type', 'uploaded_at')

admin.site.register(User, CustomUserAdmin)
admin.site.register(Vendor, VendorAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Subcategory, SubcategoryAdmin)