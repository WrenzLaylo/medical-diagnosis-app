from rest_framework import serializers
from .models import Diagnosis, Medication
from django.contrib.auth.models import User


class MedicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medication
        fields = [
            'id', 
            'medication_name', 
            'dosage', 
            'frequency', 
            'duration', 
            'instructions',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class DiagnosisSerializer(serializers.ModelSerializer):
    medications = MedicationSerializer(many=True, read_only=True)
    doctor_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Diagnosis
        fields = [
            'id', 
            'doctor', 
            'doctor_name', 
            'patient_name', 
            'patient_id',
            'symptoms', 
            'clinical_notes', 
            'ai_prediction', 
            'diagnosis_text',
            'status', 
            'created_at', 
            'updated_at', 
            'approved_at', 
            'medications'
        ]
        read_only_fields = ['id', 'ai_prediction', 'created_at', 'updated_at', 'approved_at']
    
    def get_doctor_name(self, obj):
        if obj.doctor.first_name and obj.doctor.last_name:
            return f"Dr. {obj.doctor.first_name} {obj.doctor.last_name}"
        return obj.doctor.username


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']