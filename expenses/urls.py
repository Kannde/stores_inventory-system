from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    path('',            views.expense_list,   name='expense_list'),
    path('add/',        views.expense_add,    name='expense_add'),
    path('<uuid:pk>/delete/', views.expense_delete, name='expense_delete'),
]
