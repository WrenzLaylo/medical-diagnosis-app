from django.contrib import admin
from .models import ClinicalFeedback, Diagnosis, Medication


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient_name', 'patient_id', 'doctor', 'status', 'created_at')
    search_fields = ('patient_name', 'patient_id', 'diagnosis_text', 'symptoms')
    list_filter = ('status', 'created_at')


@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'medication_name', 'diagnosis', 'dosage', 'frequency', 'duration')
    search_fields = ('medication_name', 'diagnosis__patient_name', 'diagnosis__patient_id')


@admin.register(ClinicalFeedback)
class ClinicalFeedbackAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'diagnosis',
        'source_action',
        'ai_primary_diagnosis',
        'doctor_final_diagnosis',
        'created_at',
    )
    search_fields = (
        'ai_primary_diagnosis',
        'doctor_final_diagnosis',
        'diagnosis__patient_name',
        'diagnosis__patient_id',
    )
    list_filter = ('source_action', 'created_at')
