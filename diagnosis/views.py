from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.renderers import BaseRenderer
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.contrib.auth.models import User
from .models import Diagnosis, Medication
from .serializers import DiagnosisSerializer, MedicationSerializer
from .services.hybrid_orchestrator import hybrid_orchestrator
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
    
    def get_queryset(self):
        """Filter diagnoses by query parameters"""
        queryset = Diagnosis.objects.all().order_by('-created_at')
        status_param = self.request.query_params.get('status', None)
        patient_id = self.request.query_params.get('patient_id', None)
        
        if status_param is not None:
            queryset = queryset.filter(status=status_param)
        if patient_id is not None:
            queryset = queryset.filter(patient_id=patient_id)
            
        return queryset
    
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
            
            # Log incoming data for debugging
            print("Creating diagnosis with data:", data)
            
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
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
    def approve(self, request, pk=None):
        """Approve a diagnosis"""
        diagnosis = self.get_object()
        
        if diagnosis.status == 'approved':
            return Response(
                {'message': 'Diagnosis is already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        diagnosis.status = 'approved'
        diagnosis.approved_at = timezone.now()
        diagnosis.save()
        
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
        
        # Only allow updating these fields
        allowed_fields = ['diagnosis_text', 'clinical_notes', 'medications']
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        serializer = self.get_serializer(diagnosis, data=update_data, partial=True)
        if serializer.is_valid():
            serializer.save()
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
