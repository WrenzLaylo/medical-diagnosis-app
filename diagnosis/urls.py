from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DiagnosisViewSet, MedicationViewSet

router = DefaultRouter()
router.register(r'diagnoses', DiagnosisViewSet, basename='diagnosis')
router.register(r'medications', MedicationViewSet, basename='medication')

urlpatterns = [
    path('', include(router.urls)),
]