from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/contracts/', include('contracts.urls')),
    path('api/kadastra/', include('kadastra_proxy.urls')),
    path('api/predict/', include('predict.urls')),
    path('api/', include('listings.urls')),
]
