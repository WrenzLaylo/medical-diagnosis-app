from rest_framework import serializers
from .models import Diagnosis, Medication
from django.contrib.auth.models import User
from django.db import transaction
import re


class MedicationSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    frequency = serializers.CharField(required=False, allow_blank=True)

    SCHEDULE_FIELDS = [
        'schedule_type',
        'every_hours',
        'times_per_day',
        'take_morning',
        'take_noon',
        'take_evening',
        'take_bedtime',
        'take_with_breakfast',
        'take_with_lunch',
        'take_with_dinner',
    ]

    class Meta:
        model = Medication
        fields = [
            'id', 
            'medication_name', 
            'dosage', 
            'frequency', 
            'schedule_type',
            'every_hours',
            'times_per_day',
            'take_morning',
            'take_noon',
            'take_evening',
            'take_bedtime',
            'take_with_breakfast',
            'take_with_lunch',
            'take_with_dinner',
            'duration', 
            'instructions',
            'created_at'
        ]
        read_only_fields = ['created_at']

    def validate(self, attrs):
        merged = self._merged_values(attrs)
        incoming_frequency = str(attrs.get('frequency', '')).strip()
        has_explicit_schedule_update = any(field in attrs for field in self.SCHEDULE_FIELDS)
        inferred_from_frequency = False

        if incoming_frequency and not has_explicit_schedule_update:
            inferred_schedule = self._parse_frequency_to_schedule(incoming_frequency)
            for field, value in inferred_schedule.items():
                attrs.setdefault(field, value)
            merged.update(inferred_schedule)
            inferred_from_frequency = True

        merged.update(attrs)
        if has_explicit_schedule_update:
            generated_frequency = self._build_frequency_from_schedule(merged)
            if generated_frequency:
                attrs['frequency'] = generated_frequency
            elif not incoming_frequency and not str(merged.get('frequency', '')).strip():
                raise serializers.ValidationError(
                    {'frequency': 'Provide frequency text or structured schedule details.'}
                )
        elif not incoming_frequency and not str(merged.get('frequency', '')).strip() and not inferred_from_frequency:
            raise serializers.ValidationError(
                {'frequency': 'Provide frequency text or structured schedule details.'}
            )

        return attrs

    def _merged_values(self, attrs):
        values = {}
        for field in self.Meta.fields:
            if field in attrs:
                values[field] = attrs[field]
                continue

            if self.instance is not None and hasattr(self.instance, field):
                values[field] = getattr(self.instance, field)
                continue

            if field == 'schedule_type':
                values[field] = 'free_text'
            elif field in ['every_hours', 'times_per_day', 'id', 'created_at']:
                values[field] = None
            elif field.startswith('take_'):
                values[field] = False
            else:
                values[field] = ''
        return values

    def _parse_frequency_to_schedule(self, frequency):
        frequency_lower = str(frequency or '').lower()
        parsed = {
            'schedule_type': 'free_text',
            'every_hours': None,
            'times_per_day': None,
            'take_morning': False,
            'take_noon': False,
            'take_evening': False,
            'take_bedtime': False,
            'take_with_breakfast': False,
            'take_with_lunch': False,
            'take_with_dinner': False,
        }

        hour_match = re.search(r'\b(?:every|q)\s*(\d{1,2})\s*(?:h|hr|hour|hours)\b', frequency_lower)
        if not hour_match:
            hour_match = re.search(r'\bevery\s*(\d{1,2})\s*(?:hours|hour)\b', frequency_lower)
        if hour_match:
            parsed['schedule_type'] = 'per_hour'
            parsed['every_hours'] = int(hour_match.group(1))
            return parsed

        per_day_match = re.search(r'\b(\d{1,2})\s*(?:x|times?)\s*(?:per\s*)?day\b', frequency_lower)
        if per_day_match:
            parsed['schedule_type'] = 'per_day'
            parsed['times_per_day'] = int(per_day_match.group(1))
        elif any(token in frequency_lower for token in ['four times daily', 'four times a day']):
            parsed['schedule_type'] = 'per_day'
            parsed['times_per_day'] = 4
        elif any(token in frequency_lower for token in ['three times daily', 'three times a day']):
            parsed['schedule_type'] = 'per_day'
            parsed['times_per_day'] = 3
        elif any(token in frequency_lower for token in ['twice daily', 'twice a day']):
            parsed['schedule_type'] = 'per_day'
            parsed['times_per_day'] = 2
        elif any(token in frequency_lower for token in ['once daily', 'once a day']) or re.search(r'\bdaily\b', frequency_lower):
            parsed['schedule_type'] = 'per_day'
            parsed['times_per_day'] = 1

        if re.search(r'\bbid\b', frequency_lower):
            parsed['schedule_type'] = 'per_day'
            parsed['times_per_day'] = 2
        elif re.search(r'\btid\b', frequency_lower):
            parsed['schedule_type'] = 'per_day'
            parsed['times_per_day'] = 3
        elif re.search(r'\bqid\b', frequency_lower):
            parsed['schedule_type'] = 'per_day'
            parsed['times_per_day'] = 4
        elif re.search(r'\bod\b', frequency_lower):
            parsed['schedule_type'] = 'per_day'
            parsed['times_per_day'] = 1

        timing_map = {
            'take_morning': ['morning', 'am'],
            'take_noon': ['noon', 'afternoon'],
            'take_evening': ['evening', 'night'],
            'take_bedtime': ['bedtime', 'hs', 'before sleep'],
            'take_with_breakfast': ['breakfast'],
            'take_with_lunch': ['lunch'],
            'take_with_dinner': ['dinner', 'supper'],
        }
        for field, keywords in timing_map.items():
            if any(keyword in frequency_lower for keyword in keywords):
                parsed[field] = True

        if any(parsed[field] for field in timing_map):
            parsed['schedule_type'] = 'specific_times'

        return parsed

    def _build_frequency_from_schedule(self, values):
        schedule_type = str(values.get('schedule_type', 'free_text'))

        if schedule_type == 'per_hour':
            every_hours = values.get('every_hours')
            if every_hours:
                return f'Every {every_hours} hours'
            return ''

        if schedule_type == 'per_day':
            times_per_day = values.get('times_per_day')
            if times_per_day:
                if int(times_per_day) == 1:
                    return 'Once per day'
                return f'{times_per_day} times per day'
            return ''

        if schedule_type == 'specific_times':
            labels = []
            if values.get('take_morning'):
                labels.append('morning')
            if values.get('take_noon'):
                labels.append('noon')
            if values.get('take_evening'):
                labels.append('evening')
            if values.get('take_bedtime'):
                labels.append('bedtime')
            if values.get('take_with_breakfast'):
                labels.append('with breakfast')
            if values.get('take_with_lunch'):
                labels.append('with lunch')
            if values.get('take_with_dinner'):
                labels.append('with dinner')

            if labels:
                return 'At ' + ', '.join(labels)
            return ''

        return str(values.get('frequency', '')).strip()


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
