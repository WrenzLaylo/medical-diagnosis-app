from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from .models import Diagnosis, Medication
from .ml_models.med42_service import Med42ServiceCloud


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

    def test_structured_schedule_fields_are_saved_and_frequency_is_generated(self):
        payload = {
            'doctor': self.user.id,
            'patient_name': 'Schedule Test',
            'patient_id': 'P-3003',
            'symptoms': 'Cough and fever',
            'clinical_notes': 'Outpatient follow-up.',
            'diagnosis_text': 'Viral URI',
            'status': 'pending',
            'medications': [
                {
                    'medication_name': 'Cetirizine',
                    'dosage': '10 mg',
                    'frequency': '',
                    'schedule_type': 'specific_times',
                    'take_with_lunch': True,
                    'take_bedtime': True,
                    'duration': '5 days',
                    'instructions': 'Take after meals if tolerated',
                }
            ],
        }

        response = self.client.post('/api/diagnoses/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        medication = Medication.objects.get(medication_name='Cetirizine')
        self.assertEqual(medication.schedule_type, 'specific_times')
        self.assertTrue(medication.take_with_lunch)
        self.assertTrue(medication.take_bedtime)
        self.assertIn('lunch', medication.frequency.lower())
        self.assertIn('bedtime', medication.frequency.lower())


class HybridAnalysisEndpointTests(APITestCase):
    @patch('diagnosis.views.hybrid_orchestrator.analyze')
    def test_analyze_symptoms_returns_compatibility_payload(self, mock_analyze):
        mock_analyze.return_value = {
            'result': {'primary_diagnosis': 'Pneumonia'},
            'ai_analysis': {
                'confidence_score': 0.81,
                'suggested_diagnoses': [{'term': 'Pneumonia', 'score': 0.81}],
                'keywords': ['Fever', 'Cough'],
                'interpretation': 'Validated by secondary safety layer',
                'clinical_reasoning': 'PRIMARY DIAGNOSIS: Pneumonia',
                'summary': 'Likely community acquired pneumonia',
                'recommendations': ['Chest X-ray'],
                'medications': [],
                'red_flag_analysis': {
                    'has_red_flags': False,
                    'urgency_level': 'LOW',
                    'detected_flags': [],
                },
            },
            'meta': {'validator_invoked': True},
        }

        response = self.client.post(
            '/api/diagnoses/analyze_symptoms/',
            {'symptoms': 'Fever and productive cough', 'clinical_notes': 'Crackles on exam'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['suggested_diagnoses'][0]['term'], 'Pneumonia')
        self.assertEqual(response.data['confidence_score'], 0.81)

    @patch('diagnosis.views.hybrid_orchestrator.stream_analysis')
    def test_analyze_stream_returns_sse_events(self, mock_stream_analysis):
        mock_stream_analysis.return_value = iter(
            [
                {'event': 'status', 'data': {'stage': 'intake', 'message': 'Analyzing symptoms...'}},
                {'event': 'token', 'data': {'stage': 'response', 'text': 'PRIMARY '}},
                {'event': 'token', 'data': {'stage': 'response', 'text': 'DIAGNOSIS '}},
                {
                    'event': 'done',
                    'data': {
                        'result': {'primary_diagnosis': 'Pneumonia'},
                        'ai_analysis': {'confidence_score': 0.8},
                        'meta': {'validator_invoked': True},
                    },
                },
            ]
        )

        response = self.client.post(
            '/api/diagnoses/analyze_stream/',
            {'symptoms': 'Fever and productive cough', 'clinical_notes': 'Crackles on exam'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/event-stream')

        stream_payload = b''.join(response.streaming_content).decode('utf-8')
        self.assertIn('event: status', stream_payload)
        self.assertIn('event: token', stream_payload)
        self.assertIn('event: done', stream_payload)


class Med42CriticalPrioritizationTests(APITestCase):
    def setUp(self):
        self.service = Med42ServiceCloud(api_token='test-token')

    def test_septic_shock_is_prioritized_and_comorbidities_remain_active(self):
        symptoms = (
            "Worsening confusion, generalized weakness, decreased urine output, productive cough with yellow sputum, "
            "fever 39.4 C, BP 82/48, HR 124, RR 26, SpO2 89, known type 2 diabetes and hypertension."
        )
        notes = (
            "Lethargic and disoriented. Lactate 5.8 mmol/L, WBC 19,500/uL, creatinine 2.6 mg/dL, "
            "glucose 312 mg/dL, HbA1c 9.8%, "
            "urinalysis positive leukocyte esterase and nitrites with >100 WBC/hpf, "
            "chest X-ray reveals right lower lobe consolidation."
        )
        parsed = {
            'diagnoses': [
                {'term': 'Uncontrolled type 2 diabetes mellitus', 'score': 0.90},
                {'term': 'Hypertension with renal impairment', 'score': 0.84},
                {'term': 'Pneumonia', 'score': 0.80},
            ],
            'confidence_score': 0.40,
            'interpretation': 'Low confidence',
            'recommendations': [],
            'doctor_actions': [],
            'summary': '',
        }

        self.service._apply_multimorbidity_adjustments(parsed, symptoms, notes)

        self.assertTrue(parsed.get('active_diagnoses'))
        self.assertIn('septic shock', parsed['active_diagnoses'][0].lower())
        self.assertIn('septic shock', parsed['diagnoses'][0]['term'].lower())
        self.assertTrue(
            any('uncontrolled type 2 diabetes mellitus' in term.lower() for term in parsed['active_diagnoses'])
        )
        self.assertTrue(
            any('hypertension with renal impairment' in term.lower() for term in parsed['active_diagnoses'])
        )
        self.assertGreaterEqual(parsed['confidence_score'], 0.86)

    def test_numeric_parser_accepts_comma_separated_values(self):
        value = self.service._extract_numeric_value(
            'WBC 19,500/uL',
            [r'\b(?:wbc|white blood cell(?: count)?)\s*(?:of|=|:)?\s*([0-9]{1,3}(?:,\d{3})?(?:\.\d+)?)'],
        )
        self.assertEqual(value, 19500.0)
