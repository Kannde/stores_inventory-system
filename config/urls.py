from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.static import serve

from core.views import service_worker, offline_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('sw.js', service_worker, name='service_worker'),
    path('offline/', offline_view, name='offline'),
    path('', include('core.urls')),
    path('s/<slug:store_slug>/', include('inventory.urls')),
    path('s/<slug:store_slug>/sales/', include('sales.urls')),
    path('s/<slug:store_slug>/preorders/', include('preorders.urls')),
    path('s/<slug:store_slug>/reports/', include('reports.urls')),
    path('s/<slug:store_slug>/expenses/', include('expenses.urls')),
    path('s/<slug:store_slug>/procurement/', include('procurement.urls')),
    path('s/<slug:store_slug>/shipments/', include('shipments.urls')),
    path('s/<slug:store_slug>/payments/', include('payments.urls')),
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
]
