# Generated by Django 5.2.1 on 2025-05-29 06:46

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_tag_product_compare_at_price_product_cost_per_item_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='canonical_url',
        ),
        migrations.RemoveField(
            model_name='product',
            name='meta_description',
        ),
        migrations.RemoveField(
            model_name='product',
            name='meta_keywords',
        ),
        migrations.RemoveField(
            model_name='product',
            name='meta_title',
        ),
        migrations.CreateModel(
            name='ProductFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='product_files/')),
                ('file_name', models.CharField(max_length=255)),
                ('file_type', models.CharField(max_length=50)),
                ('file_size', models.IntegerField()),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='files', to='accounts.product')),
            ],
            options={
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
