from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('s/<slug:store_slug>/', include('inventory.urls')),
    path('s/<slug:store_slug>/sales/', include('sales.urls')),
    path('s/<slug:store_slug>/preorder/', include('preorders.urls')),
    path('s/<slug:store_slug>/reports/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
