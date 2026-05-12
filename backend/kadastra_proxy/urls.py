from django.urls import path
from . import views

urlpatterns = [
    path('analyze', views.analyze, name='kadastra_analyze'),
    path('quick-analyze', views.quick_analyze, name='kadastra_quick_analyze'),
    path('health', views.health, name='kadastra_health'),
]
