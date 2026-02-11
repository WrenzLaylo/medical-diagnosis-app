from rest_framework import serializers
from .models import Diagnosis, Medication
from django.contrib.auth.models import User
from django.db import transaction


class MedicationSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

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
        read_only_fields = ['created_at']


class DiagnosisSerializer(serializers.ModelSerializer):
    medications = MedicationSerializer(many=True, required=False)
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
        read_only_fields = ['id', 'created_at', 'updated_at', 'approved_at']

    def create(self, validated_data):
        medications_data = validated_data.pop('medications', [])
        with transaction.atomic():
            diagnosis = Diagnosis.objects.create(**validated_data)
            self._sync_medications(diagnosis, medications_data)
        return diagnosis

    def update(self, instance, validated_data):
        medications_data = validated_data.pop('medications', None)

        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()

            if medications_data is not None:
                self._sync_medications(instance, medications_data)

        return instance

    def _sync_medications(self, diagnosis, medications_data):
        retained_ids = []

        for med_data in medications_data:
            medication_id = med_data.pop('id', None)
            medication = None

            if medication_id is not None:
                medication = diagnosis.medications.filter(id=medication_id).first()

            if medication is None:
                medication = Medication.objects.create(diagnosis=diagnosis, **med_data)
            else:
                for field, value in med_data.items():
                    setattr(medication, field, value)
                medication.save()

            retained_ids.append(medication.id)

        diagnosis.medications.exclude(id__in=retained_ids).delete()
    
    def get_doctor_name(self, obj):
        if obj.doctor.first_name and obj.doctor.last_name:
            return f"Dr. {obj.doctor.first_name} {obj.doctor.last_name}"
        return obj.doctor.username


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
