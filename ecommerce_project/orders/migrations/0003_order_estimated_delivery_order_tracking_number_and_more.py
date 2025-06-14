# Generated by Django 5.2.1 on 2025-06-02 09:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_remove_order_product_remove_order_quantity_and_more'),
        ('vendors', '0002_vendor_banner_vendor_business_address_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='estimated_delivery',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='tracking_number',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='commission_fee',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='vendor',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='vendors.vendor'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='orderitem',
            name='vendor_paid',
            field=models.BooleanField(default=False),
        ),
    ]
