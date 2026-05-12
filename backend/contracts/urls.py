from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.generate_contract_view, name='contract-generate'),
    path('chat/', views.chat_contract_view, name='contract-chat'),
    path('pdf/', views.download_pdf_view, name='contract-pdf'),
    path('map/', views.map_view, name='incidents-map'),
]
