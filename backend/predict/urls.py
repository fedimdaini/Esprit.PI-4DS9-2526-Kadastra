from django.urls import path
from . import views

urlpatterns = [
    path('forecast/map/', views.forecast_map, name='forecast_map'),
]
