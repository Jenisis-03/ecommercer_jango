from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_product, name='upload_product'),
    path('list/', views.product_list, name='product_list'),
    path('<int:product_id>/', views.product_detail, name='product_detail'),
]