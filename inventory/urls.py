from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_form, name='product_add'),
    path('products/<uuid:pk>/edit/', views.product_form, name='product_edit'),
    path('products/<uuid:pk>/stock/', views.stock_adjust, name='stock_adjust'),
    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_form, name='category_add'),
    # Packages
    path('packages/', views.package_list, name='package_list'),
    path('packages/add/', views.package_form, name='package_add'),
    path('packages/<uuid:pk>/edit/', views.package_form, name='package_edit'),
    # Stock overview
    path('stock/', views.stock_overview, name='stock_overview'),
    # Suppliers
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_form, name='supplier_add'),
    path('suppliers/<uuid:pk>/', views.supplier_detail, name='supplier_detail'),
    path('suppliers/<uuid:pk>/edit/', views.supplier_form, name='supplier_edit'),
    path('suppliers/<uuid:pk>/transact/', views.supplier_transact, name='supplier_transact'),
    path('suppliers/<uuid:pk>/toggle/', views.supplier_toggle, name='supplier_toggle'),
    # Barcode
    path('products/<uuid:pk>/barcode/', views.barcode_print, name='barcode_print'),
    # API endpoints for AJAX
    path('api/products/', views.api_products, name='api_products'),
    path('api/packages/', views.api_packages, name='api_packages'),
]
