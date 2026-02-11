from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Diagnosis, Medication


class DiagnosisMedicationIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='doctor_test',
            password='password123',
            first_name='Test',
            last_name='Doctor',
        )

    def test_create_diagnosis_with_nested_medications_and_ai_prediction(self):
        payload = {
            'doctor': self.user.id,
            'patient_name': 'John Doe',
            'patient_id': 'P-1001',
            'symptoms': 'Fever, cough, shortness of breath',
            'clinical_notes': 'Possible community acquired pneumonia.',
            'diagnosis_text': 'Community acquired pneumonia',
            'status': 'pending',
            'ai_prediction': {
                'confidence_score': 0.82,
                'suggested_diagnoses': [{'term': 'Pneumonia', 'score': 0.82}],
                'medications': [
                    {
                        'medication_name': 'Amoxicillin-Clavulanate',
                        'dosage': '875/125 mg',
                        'frequency': 'PO every 12 hours',
                        'duration': '7 days',
                        'instructions': 'Take with food',
                    }
                ],
            },
            'medications': [
                {
                    'medication_name': 'Amoxicillin-Clavulanate',
                    'dosage': '875/125 mg',
                    'frequency': 'PO every 12 hours',
                    'duration': '7 days',
                    'instructions': 'Take with food',
                },
                {
                    'medication_name': 'Paracetamol',
                    'dosage': '500 mg',
                    'frequency': 'PO every 6 hours PRN',
                    'duration': '3 days',
                    'instructions': 'For fever',
                },
            ],
        }

        response = self.client.post('/api/diagnoses/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Diagnosis.objects.count(), 1)
        self.assertEqual(Medication.objects.count(), 2)

        diagnosis = Diagnosis.objects.get()
        self.assertEqual(diagnosis.patient_name, 'John Doe')
        self.assertIsNotNone(diagnosis.ai_prediction)
        self.assertEqual(diagnosis.ai_prediction.get('confidence_score'), 0.82)

        meds = list(
            diagnosis.medications.order_by('medication_name').values_list(
                'medication_name',
                flat=True,
            )
        )
        self.assertEqual(meds, ['Amoxicillin-Clavulanate', 'Paracetamol'])

    def test_update_diagnosis_replaces_and_updates_medications(self):
        diagnosis = Diagnosis.objects.create(
            doctor=self.user,
            patient_name='Jane Doe',
            patient_id='P-2002',
            symptoms='Wheezing and dyspnea',
            clinical_notes='Known asthma, no fever',
            diagnosis_text='Asthma exacerbation',
            status='pending',
        )
        existing_med = Medication.objects.create(
            diagnosis=diagnosis,
            medication_name='Albuterol inhaler',
            dosage='90 mcg/puff',
            frequency='1-2 puffs every 4-6 hours PRN',
            duration='As needed',
            instructions='Rescue inhaler',
        )
        Medication.objects.create(
            diagnosis=diagnosis,
            medication_name='Prednisone',
            dosage='20 mg',
            frequency='PO once daily',
            duration='5 days',
            instructions='Take in the morning',
        )

        patch_payload = {
            'diagnosis_text': 'Acute asthma exacerbation',
            'clinical_notes': 'Improved after bronchodilator treatment.',
            'medications': [
                {
                    'id': existing_med.id,
                    'medication_name': 'Albuterol inhaler',
                    'dosage': '2 puffs',
                    'frequency': 'every 4 hours PRN',
                    'duration': 'As needed',
                    'instructions': 'Use spacer',
                },
                {
                    'medication_name': 'Budesonide inhaler',
                    'dosage': '200 mcg',
                    'frequency': '2 puffs twice daily',
                    'duration': '30 days',
                    'instructions': 'Controller therapy',
                },
            ],
        }

        response = self.client.patch(
            f'/api/diagnoses/{diagnosis.id}/update_diagnosis/',
            patch_payload,
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        diagnosis.refresh_from_db()
        self.assertEqual(diagnosis.diagnosis_text, 'Acute asthma exacerbation')
        self.assertEqual(diagnosis.clinical_notes, 'Improved after bronchodilator treatment.')
        self.assertEqual(diagnosis.medications.count(), 2)

        updated_existing_med = diagnosis.medications.get(medication_name='Albuterol inhaler')
        self.assertEqual(updated_existing_med.dosage, '2 puffs')
        self.assertEqual(updated_existing_med.frequency, 'every 4 hours PRN')

        self.assertTrue(
            diagnosis.medications.filter(medication_name='Budesonide inhaler').exists()
        )
        self.assertFalse(
            diagnosis.medications.filter(medication_name='Prednisone').exists()
        )
