from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
   
    list_display = ('email', 'is_staff', 'is_superuser', 'is_active')

    
    search_fields = ('email',)


    ordering = ('email',)

    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'is_active')}),
        ('Vendor Information', {'fields': ('is_vendor', 'shop_name', 'shop_address')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
        ('Permissions', {
            'fields': ('is_staff', 'is_superuser', 'is_active')
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)