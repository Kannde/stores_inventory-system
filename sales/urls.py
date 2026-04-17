from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.sale_list, name='sale_list'),
    path('new/', views.new_sale, name='new_sale'),
    path('<uuid:pk>/', views.sale_detail, name='sale_detail'),
    path('<uuid:pk>/receipt/', views.sale_receipt, name='sale_receipt'),
    path('api/checkout/', views.api_checkout, name='api_checkout'),
    path('credit/', views.credit_list, name='credit_list'),
    path('credit/<uuid:pk>/pay/', views.credit_payment, name='credit_payment'),
]
