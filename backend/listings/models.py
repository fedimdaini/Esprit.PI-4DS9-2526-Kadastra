from django.db import models

class Data(models.Model):
    titre = models.TextField(blank=True, null=True)
    lien = models.TextField(unique=True, blank=True, null=True)
    prix = models.TextField(blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    localisation = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    pieces = models.TextField(blank=True, null=True)
    chambres = models.TextField(blank=True, null=True)
    salles_de_bain = models.TextField(blank=True, null=True)
    surface = models.TextField(blank=True, null=True)
    type = models.TextField(blank=True, null=True)
    date_post = models.DateField(blank=True, null=True)
    
    class Meta:
        managed = False
        db_table = 'data'
    
    def __str__(self):
        return self.titre or f"Annonce #{self.id}"
    
    @property
    def source(self):
        """Détecte la source depuis le lien"""
        if self.lien and 'mubawab' in self.lien.lower():
            return 'mubawab'
        elif self.lien and 'tayara' in self.lien.lower():
            return 'tayara'
        return 'unknown'
    
    @property
    def image_extension(self):
        """Retourne l'extension selon la source"""
        return 'avif' if self.source == 'mubawab' else 'jpg'
    
    @property
    def first_image(self):
        """URL de la première image via le proxy Django"""
        return f"/api/images/{self.id}/1/{self.image_extension}/"
    
    def get_images_urls(self, max_images=20):
        """Liste des URLs d'images via le proxy Django"""
        ext = self.image_extension
        return [f"/api/images/{self.id}/{i}/{ext}/" for i in range(1, max_images + 1)]