from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin-landing/', views.admin_landing, name='admin_landing'),
    path('admin-landing/stores/new/', views.admin_store_create, name='admin_store_create'),
    path('admin-landing/stores/<uuid:pk>/edit/', views.admin_store_edit, name='admin_store_edit'),
    path('admin-landing/stores/<uuid:pk>/toggle/', views.admin_store_toggle, name='admin_store_toggle'),
    path('admin-landing/owners/', views.admin_owners, name='admin_owners'),
    path('admin-landing/owners/new/', views.admin_owner_create, name='admin_owner_create'),
    path('admin-landing/owners/<int:pk>/edit/', views.admin_owner_edit, name='admin_owner_edit'),
    path('admin-landing/logs/', views.admin_logs, name='admin_logs'),
    path('s/<slug:store_slug>/dashboard/', views.store_dashboard, name='store_dashboard'),
    path('s/<slug:store_slug>/settings/', views.store_settings, name='store_settings'),
    path('s/<slug:store_slug>/staff/', views.staff_list, name='staff_list'),
    path('s/<slug:store_slug>/staff/add/', views.staff_add, name='staff_add'),
    path('s/<slug:store_slug>/staff/<uuid:pk>/edit/', views.staff_edit, name='staff_edit'),
    path('s/<slug:store_slug>/staff/<uuid:pk>/toggle/', views.staff_toggle, name='staff_toggle'),
    path('s/<slug:store_slug>/staff/<uuid:pk>/reset-password/', views.staff_reset_password, name='staff_reset_password'),
    path('s/<slug:store_slug>/change-password/', views.change_password, name='change_password'),
]
