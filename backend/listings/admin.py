from django.contrib import admin
from .models import Data

@admin.register(Data)
class DataAdmin(admin.ModelAdmin):
    list_display = ['id', 'titre', 'type', 'localisation', 'prix', 'date_post']
    list_filter = ['type', 'localisation']
    search_fields = ['titre', 'description']