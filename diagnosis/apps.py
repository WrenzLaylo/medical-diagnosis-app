from django.apps import AppConfig


class DiagnosisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'diagnosis'
    
    def ready(self):
        """Initialize the Med42 model when Django starts"""
        pass