from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/sales-chart/', views.api_sales_chart, name='api_sales_chart'),
    path('api/top-products/', views.api_top_products, name='api_top_products'),
]
