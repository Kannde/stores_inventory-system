from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('skroda/webhook/', views.skroda_webhook, name='skroda_webhook'),
    path('skroda/<uuid:sale_id>/success/', views.payment_success, name='payment_success'),
    path('skroda/<uuid:sale_id>/cancelled/', views.payment_cancelled, name='payment_cancelled'),
]
