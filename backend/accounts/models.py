from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    4 types d'utilisateurs:
    - PARTICULIER: achète/vend pour usage personnel
    - INVESTISSEUR: investit dans l'immobilier
    - AGENT: agent immobilier professionnel
    - BANQUIER: banquier qui finance les transactions
    """
    USER_TYPE_CHOICES = [
        ('PARTICULIER', 'Particulier'),
        ('INVESTISSEUR', 'Investisseur'),
        ('AGENT', 'Agent immobilier'),
        ('BANQUIER', 'Banquier'),
    ]
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='PARTICULIER')
    phone = models.CharField(max_length=20, blank=True, null=True)
    cin = models.CharField(max_length=20, blank=True, null=True, verbose_name="CIN")
    address = models.TextField(blank=True, null=True, verbose_name="Adresse")
    
    # Pour agents
    agency_name = models.CharField(max_length=200, blank=True, null=True)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    
    # Pour banquiers
    bank_name = models.CharField(max_length=200, blank=True, null=True)
    branch = models.CharField(max_length=200, blank=True, null=True)
    
    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"
    
    @property
    def is_normal_user(self):
        return self.user_type in ['PARTICULIER', 'INVESTISSEUR']
    
    @property
    def is_pro_user(self):
        return self.user_type in ['AGENT', 'BANQUIER']
