from django.urls import path
from . import views

app_name = 'preorders'

urlpatterns = [
    path('', views.preorder_form, name='preorder_form'),  # Public form
    path('success/', views.preorder_success, name='preorder_success'),
    path('manage/', views.preorder_list, name='preorder_list'),  # Staff view
    path('<uuid:pk>/', views.preorder_detail, name='preorder_detail'),
    path('<uuid:pk>/status/', views.preorder_status, name='preorder_status'),
]
