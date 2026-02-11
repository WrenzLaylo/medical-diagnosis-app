from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Diagnosis(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
    ]
    
    doctor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='diagnoses')
    patient_name = models.CharField(max_length=200)
    patient_id = models.CharField(max_length=100)
    symptoms = models.TextField()
    clinical_notes = models.TextField(blank=True)
    ai_prediction = models.JSONField(null=True, blank=True)
    diagnosis_text = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Diagnoses'
    
    def __str__(self):
        return f"{self.patient_name} - {self.created_at.strftime('%Y-%m-%d')}"


class Medication(models.Model):
    SCHEDULE_TYPE_CHOICES = [
        ('free_text', 'Free Text'),
        ('per_hour', 'Per Hour'),
        ('per_day', 'Per Day'),
        ('specific_times', 'Specific Times'),
    ]

    diagnosis = models.ForeignKey(Diagnosis, on_delete=models.CASCADE, related_name='medications')
    medication_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES, default='free_text')
    every_hours = models.PositiveSmallIntegerField(null=True, blank=True)
    times_per_day = models.PositiveSmallIntegerField(null=True, blank=True)
    take_morning = models.BooleanField(default=False)
    take_noon = models.BooleanField(default=False)
    take_evening = models.BooleanField(default=False)
    take_bedtime = models.BooleanField(default=False)
    take_with_breakfast = models.BooleanField(default=False)
    take_with_lunch = models.BooleanField(default=False)
    take_with_dinner = models.BooleanField(default=False)
    duration = models.CharField(max_length=100)
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.medication_name} for {self.diagnosis.patient_name}"
