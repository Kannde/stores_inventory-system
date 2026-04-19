from django.urls import path
from . import views

app_name = 'procurement'

urlpatterns = [
    path('',                    views.plan_list,    name='plan_list'),
    path('new/',                views.plan_create,  name='plan_create'),
    path('<uuid:pk>/',          views.plan_detail,  name='plan_detail'),
    path('<uuid:pk>/edit/',     views.plan_edit,    name='plan_edit'),
    path('<uuid:pk>/fulfil/',   views.plan_fulfil,  name='plan_fulfil'),
    path('<uuid:pk>/status/',   views.plan_status,  name='plan_status'),
]
