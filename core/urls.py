from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('s/<slug:store_slug>/dashboard/', views.store_dashboard, name='store_dashboard'),
    path('s/<slug:store_slug>/staff/', views.staff_list, name='staff_list'),
    path('s/<slug:store_slug>/staff/add/', views.staff_add, name='staff_add'),
    path('s/<slug:store_slug>/staff/<uuid:pk>/edit/', views.staff_edit, name='staff_edit'),
    path('s/<slug:store_slug>/staff/<uuid:pk>/toggle/', views.staff_toggle, name='staff_toggle'),
]
