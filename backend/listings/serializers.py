from rest_framework import serializers
from .models import Data

class DataSerializer(serializers.ModelSerializer):
    first_image = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    source = serializers.SerializerMethodField()
    
    class Meta:
        model = Data
        fields = '__all__'
    
    def get_first_image(self, obj):
        return obj.first_image
    
    def get_images(self, obj):
        return obj.get_images_urls()
    
    def get_source(self, obj):
        return obj.source