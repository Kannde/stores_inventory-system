from django.urls import path

from . import views

app_name = 'shipments'

urlpatterns = [
    path('', views.shipment_list, name='shipment_list'),
    path('new/', views.shipment_form, name='shipment_add'),
    path('<uuid:pk>/', views.shipment_detail, name='shipment_detail'),
    path('<uuid:pk>/edit/', views.shipment_form, name='shipment_edit'),
    path('<uuid:pk>/status/', views.shipment_status, name='shipment_status'),
    path('packages/<uuid:pk>/receive/', views.package_receive, name='package_receive'),
    path('api/shipments/', views.api_shipments, name='api_shipments'),
    path('api/shipments/<uuid:pk>/', views.api_shipment_detail, name='api_shipment_detail'),
    path('api/packages/', views.api_packages, name='api_packages'),
]

