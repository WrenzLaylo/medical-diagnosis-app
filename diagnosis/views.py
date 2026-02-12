from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.renderers import BaseRenderer
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.contrib.auth.models import User
from .models import ClinicalFeedback, Diagnosis, Medication
from .serializers import DiagnosisSerializer, MedicationSerializer
from .services.hybrid_orchestrator import hybrid_orchestrator
from .services.medication_safety import MedicationSafetyEngine
import json
import traceback


class ServerSentEventRenderer(BaseRenderer):
    media_type = 'text/event-stream'
    format = 'event-stream'
    charset = 'utf-8'
    render_style = 'text'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if data is None:
            return b''
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        return str(data).encode(self.charset)


class DiagnosisViewSet(viewsets.ModelViewSet):
    queryset = Diagnosis.objects.all()
    serializer_class = DiagnosisSerializer
    medication_safety_engine = MedicationSafetyEngine()
    
    def get_queryset(self):
        """Filter diagnoses by query parameters"""
        queryset = (
            Diagnosis.objects.select_related('doctor')
            .prefetch_related('medications', 'feedback_entries')
            .order_by('-created_at')
        )
        status_param = self.request.query_params.get('status', None)
        patient_id = self.request.query_params.get('patient_id', None)
        
        if status_param is not None:
            queryset = queryset.filter(status=status_param)
        if patient_id is not None:
            queryset = queryset.filter(patient_id=patient_id)
            
        return queryset

    def _normalize_text(self, value: str) -> str:
        return ' '.join(str(value or '').lower().split())

    def _diagnosis_match(self, left: str, right: str) -> bool:
        l = self._normalize_text(left)
        r = self._normalize_text(right)
        if not l or not r:
            return False
        return l == r or l in r or r in l

    def _serialize_ai_medications(self, ai_prediction: dict) -> list:
        if not isinstance(ai_prediction, dict):
            return []
        meds = ai_prediction.get('medications', [])
        serialized = []
        if not isinstance(meds, list):
            return serialized
        for med in meds[:8]:
            if not isinstance(med, dict):
                continue
            serialized.append(
                {
                    'medication_name': str(
                        med.get('medication_name')
                        or med.get('name')
                        or ''
                    ).strip(),
                    'dosage': str(med.get('dosage', '')).strip(),
                    'frequency': str(med.get('frequency', '')).strip(),
                    'duration': str(med.get('duration', '')).strip(),
                    'instructions': str(med.get('instructions', '')).strip(),
                }
            )
        return serialized

    def _serialize_doctor_medications(self, diagnosis: Diagnosis) -> list:
        meds = diagnosis.medications.all()[:12]
        serialized = []
        for med in meds:
            serialized.append(
                {
                    'medication_name': med.medication_name,
                    'dosage': med.dosage,
                    'frequency': med.frequency,
                    'duration': med.duration,
                    'instructions': med.instructions,
                }
            )
        return serialized

    def _update_medication_safety_snapshot(self, diagnosis: Diagnosis) -> None:
        ai_prediction = diagnosis.ai_prediction if isinstance(diagnosis.ai_prediction, dict) else {}
        medications = self._serialize_doctor_medications(diagnosis) or self._serialize_ai_medications(ai_prediction)
        if not ai_prediction and not medications:
            return
        context = f"{diagnosis.symptoms}\n{diagnosis.clinical_notes}".strip()
        medication_safety = self.medication_safety_engine.assess(medications, context)
        ai_prediction['medication_safety'] = medication_safety
        diagnosis.ai_prediction = ai_prediction
        diagnosis.save(update_fields=['ai_prediction', 'updated_at'])

    def destroy(self, request, *args, **kwargs):
        diagnosis = self.get_object()
        if diagnosis.status != 'draft':
            return Response(
                {'message': 'Only draft diagnoses can be deleted.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        self.perform_destroy(diagnosis)
        return Response({'message': 'Draft deleted successfully'}, status=status.HTTP_200_OK)

    def _capture_feedback_entry(self, diagnosis: Diagnosis, source_action: str, feedback_note: str = '') -> None:
        ai_prediction = diagnosis.ai_prediction if isinstance(diagnosis.ai_prediction, dict) else {}
        if not ai_prediction:
            return

        ai_active = []
        for item in ai_prediction.get('active_diagnoses', [])[:6]:
            value = str(item).strip()
            if value:
                ai_active.append(value)

        ai_suggested = []
        for item in ai_prediction.get('suggested_diagnoses', [])[:6]:
            if not isinstance(item, dict):
                continue
            term = str(item.get('term', '')).strip()
            if term:
                ai_suggested.append(term)

        combined_ai_suggested = []
        seen = set()
        for term in ai_active + ai_suggested:
            key = self._normalize_text(term)
            if not key or key in seen:
                continue
            seen.add(key)
            combined_ai_suggested.append(term)

        ai_primary = combined_ai_suggested[0] if combined_ai_suggested else ''
        doctor_final = str(diagnosis.diagnosis_text or '').strip()
        if not doctor_final:
            return

        ai_medications = self._serialize_ai_medications(ai_prediction)
        doctor_medications = self._serialize_doctor_medications(diagnosis)

        ai_med_names = sorted(
            {
                self._normalize_text(med.get('medication_name', ''))
                for med in ai_medications
                if med.get('medication_name')
            }
        )
        doctor_med_names = sorted(
            {
                self._normalize_text(med.get('medication_name', ''))
                for med in doctor_medications
                if med.get('medication_name')
            }
        )
        diagnosis_changed = bool(combined_ai_suggested) and not any(
            self._diagnosis_match(candidate, doctor_final) for candidate in combined_ai_suggested[:6]
        )
        medications_changed = ai_med_names != doctor_med_names

        correction_flags = []
        if diagnosis_changed:
            correction_flags.append('diagnosis_changed')
        else:
            correction_flags.append('diagnosis_confirmed')
        if medications_changed:
            correction_flags.append('medications_changed')
        if feedback_note.strip():
            correction_flags.append('doctor_note_added')

        summary_parts = []
        if diagnosis_changed:
            summary_parts.append(f"Doctor changed AI diagnosis from '{ai_primary or 'n/a'}' to '{doctor_final}'.")
        else:
            summary_parts.append('Doctor kept AI primary diagnosis.')
        if medications_changed:
            summary_parts.append('Doctor adjusted medication plan.')
        elif doctor_med_names:
            summary_parts.append('Medication plan remained aligned with AI suggestions.')
        if feedback_note.strip():
            summary_parts.append(f"Doctor note: {feedback_note.strip()[:240]}")

        ClinicalFeedback.objects.create(
            diagnosis=diagnosis,
            source_action=source_action,
            symptom_signature=(diagnosis.symptoms or '')[:1200],
            ai_primary_diagnosis=ai_primary[:255],
            doctor_final_diagnosis=doctor_final[:255],
            ai_suggested_diagnoses=combined_ai_suggested,
            ai_medications=ai_medications,
            doctor_medications=doctor_medications,
            correction_flags=correction_flags,
            correction_summary=' '.join(summary_parts)[:1500],
            feedback_note=feedback_note.strip()[:1000],
        )
    
    @action(detail=False, methods=['post'])
    def analyze_symptoms(self, request):
        """
        Analyze symptoms through hybrid pipeline (Med42 + optional watsonx validation)
        Returns frontend-compatible AI analysis payload
        """
        symptoms = request.data.get('symptoms', '')
        clinical_notes = request.data.get('clinical_notes', '')
        
        if not symptoms:
            return Response(
                {'error': 'Symptoms are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            payload = hybrid_orchestrator.analyze(symptoms, clinical_notes)
            ai_analysis = payload.get('ai_analysis', {})
            return Response(ai_analysis, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error in analyze_symptoms: {e}")
            traceback.print_exc()
            return Response(
                {
                    'error': f'Analysis failed: {str(e)}',
                    'confidence_score': 0.0,
                    'suggested_diagnoses': [],
                    'keywords': [],
                    'interpretation': 'Analysis failed',
                    'clinical_reasoning': '',
                    'medications': []
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], renderer_classes=[ServerSentEventRenderer])
    def analyze_stream(self, request):
        """
        Stream hybrid analysis via Server-Sent Events (SSE).
        Event types: status, token, validation, done, error
        """
        symptoms = request.data.get('symptoms', '')
        clinical_notes = request.data.get('clinical_notes', '')

        if not symptoms:
            return Response(
                {'error': 'Symptoms are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        def format_sse(event_name, data):
            return f"event: {event_name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        def event_stream():
            try:
                for event in hybrid_orchestrator.stream_analysis(
                    symptoms=symptoms,
                    clinical_notes=clinical_notes,
                    include_tokens=True,
                ):
                    yield format_sse(event.get('event', 'status'), event.get('data', {}))
            except Exception as exc:
                yield format_sse('error', {'message': f'Analysis failed: {exc}'})
                yield format_sse(
                    'done',
                    {
                        'result': {},
                        'ai_analysis': {
                            'error': f'Analysis failed: {exc}',
                            'confidence_score': 0.0,
                            'suggested_diagnoses': [],
                            'keywords': [],
                            'interpretation': 'Analysis failed',
                            'clinical_reasoning': '',
                            'summary': '',
                            'recommendations': [],
                            'medications': [],
                            'red_flag_analysis': {
                                'has_red_flags': False,
                                'urgency_level': 'UNKNOWN',
                                'detected_flags': [],
                            },
                        },
                        'meta': {'cache_hit': False, 'validator_invoked': False},
                    }
                )

        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
    
    def create(self, request, *args, **kwargs):
        """Create diagnosis with enhanced error handling and automatic doctor assignment"""
        try:
            feedback_note = str(request.data.get('feedback_note', '')).strip()

            # Get or create a default doctor user if not provided
            doctor_id = request.data.get('doctor')
            if not doctor_id:
                # Get or create default user
                default_user, created = User.objects.get_or_create(
                    username='default_doctor',
                    defaults={
                        'first_name': 'Default',
                        'last_name': 'Doctor',
                        'email': 'doctor@example.com'
                    }
                )
                # Create a mutable copy of request.data
                data = request.data.copy()
                data['doctor'] = default_user.id
            else:
                # Verify doctor exists, if not create default
                try:
                    User.objects.get(id=doctor_id)
                    data = request.data.copy()
                except User.DoesNotExist:
                    print(f"Doctor ID {doctor_id} not found, using default doctor")
                    default_user, created = User.objects.get_or_create(
                        username='default_doctor',
                        defaults={
                            'first_name': 'Default',
                            'last_name': 'Doctor',
                            'email': 'doctor@example.com'
                        }
                    )
                    data = request.data.copy()
                    data['doctor'] = default_user.id

            if isinstance(data, dict):
                data.pop('feedback_note', None)
            else:
                try:
                    data.pop('feedback_note')
                except Exception:
                    pass
            
            # Log incoming data for debugging
            print("Creating diagnosis with data:", data)
            
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            diagnosis = serializer.instance
            if diagnosis is not None:
                self._update_medication_safety_snapshot(diagnosis)
                if diagnosis.status != 'draft':
                    self._capture_feedback_entry(diagnosis, source_action='create', feedback_note=feedback_note)
            
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
                headers=headers
            )
        except Exception as e:
            print(f"Error creating diagnosis: {e}")
            traceback.print_exc()
            return Response(
                {'error': str(e), 'detail': traceback.format_exc()},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def submit_for_review(self, request, pk=None):
        """Move a draft diagnosis to pending review."""
        diagnosis = self.get_object()
        feedback_note = str(request.data.get('feedback_note', '')).strip()

        if diagnosis.status == 'approved':
            return Response(
                {'message': 'Approved diagnoses cannot be submitted for review.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if diagnosis.status == 'pending':
            serializer = self.get_serializer(diagnosis)
            return Response(
                {'message': 'Diagnosis is already pending review.', 'data': serializer.data},
                status=status.HTTP_200_OK
            )

        final_diagnosis = str(diagnosis.diagnosis_text or '').strip().lower()
        if not final_diagnosis or final_diagnosis == 'draft - pending final diagnosis':
            return Response(
                {'message': 'Please provide a final diagnosis before submitting for review.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        diagnosis.status = 'pending'
        diagnosis.approved_at = None
        diagnosis.save(update_fields=['status', 'approved_at', 'updated_at'])
        self._update_medication_safety_snapshot(diagnosis)
        self._capture_feedback_entry(diagnosis, source_action='update', feedback_note=feedback_note)

        serializer = self.get_serializer(diagnosis)
        return Response(
            {'message': 'Draft submitted for review successfully', 'data': serializer.data},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def reanalyze(self, request, pk=None):
        """Run AI analysis for an existing diagnosis and persist ai_prediction."""
        diagnosis = self.get_object()
        symptoms = str(diagnosis.symptoms or '').strip()
        clinical_notes = str(diagnosis.clinical_notes or '').strip()

        if not symptoms:
            return Response(
                {'message': 'Symptoms are required to run AI analysis.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            payload = hybrid_orchestrator.analyze(symptoms=symptoms, clinical_notes=clinical_notes)
            ai_analysis = payload.get('ai_analysis', {})
            if not isinstance(ai_analysis, dict):
                ai_analysis = {}

            diagnosis.ai_prediction = ai_analysis
            diagnosis.save(update_fields=['ai_prediction', 'updated_at'])
            self._update_medication_safety_snapshot(diagnosis)

            serializer = self.get_serializer(diagnosis)
            return Response(
                {
                    'message': 'AI analysis updated successfully',
                    'ai_analysis': ai_analysis,
                    'data': serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            print(f"Error reanalyzing diagnosis #{diagnosis.id}: {exc}")
            traceback.print_exc()
            return Response(
                {'message': f'AI reanalysis failed: {exc}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a diagnosis"""
        diagnosis = self.get_object()
        feedback_note = str(request.data.get('feedback_note', '')).strip()
        
        if diagnosis.status == 'approved':
            return Response(
                {'message': 'Diagnosis is already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if diagnosis.status == 'draft':
            return Response(
                {'message': 'Submit draft for review before approval.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        diagnosis.status = 'approved'
        diagnosis.approved_at = timezone.now()
        diagnosis.save()
        self._update_medication_safety_snapshot(diagnosis)
        self._capture_feedback_entry(diagnosis, source_action='approve', feedback_note=feedback_note)
        
        serializer = self.get_serializer(diagnosis)
        return Response({
            'message': 'Diagnosis approved successfully',
            'data': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def add_medication(self, request, pk=None):
        """Add medication to a diagnosis"""
        diagnosis = self.get_object()
        
        medication_data = request.data.copy()
        
        serializer = MedicationSerializer(data=medication_data)
        if serializer.is_valid():
            serializer.save(diagnosis=diagnosis)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        print(f"Medication validation errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch'])
    def update_diagnosis(self, request, pk=None):
        """Update diagnosis details including medications"""
        diagnosis = self.get_object()
        feedback_note = str(request.data.get('feedback_note', '')).strip()
        
        # Only allow updating these fields
        allowed_fields = ['diagnosis_text', 'clinical_notes', 'medications']
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = self.get_serializer(diagnosis, data=update_data, partial=True)
        if serializer.is_valid():
            serializer.save()
            updated = serializer.instance
            if updated is not None:
                self._update_medication_safety_snapshot(updated)
                if updated.status != 'draft':
                    self._capture_feedback_entry(updated, source_action='update', feedback_note=feedback_note)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MedicationViewSet(viewsets.ModelViewSet):
    queryset = Medication.objects.all()
    serializer_class = MedicationSerializer
    
    def get_queryset(self):
        """Filter medications by diagnosis_id"""
        queryset = Medication.objects.all()
        diagnosis_id = self.request.query_params.get('diagnosis_id', None)
        
        if diagnosis_id is not None:
            queryset = queryset.filter(diagnosis_id=diagnosis_id)
            
        return queryset
