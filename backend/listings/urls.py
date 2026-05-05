from django.urls import path
from . import views

urlpatterns = [
    path('listings/', views.listings_view, name='listings'),
    path('listings/<int:pk>/', views.listing_detail_view, name='listing-detail'),
    path('stats/', views.stats_view, name='stats'),
    path('filter-options/', views.filter_options_view, name='filter-options'),
    path('images/<int:listing_id>/<int:image_num>/<str:extension>/', views.proxy_image_view, name='proxy-image'),
]