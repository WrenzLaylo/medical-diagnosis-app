import React, { useState } from 'react';
import { diagnosisAPI } from '../services/api';
import { formatAIOutput, safeNumber, formatPercentage } from '../utils/formatUtils';
import { useFeedback } from './ui/FeedbackProvider';
import {
  defaultMedicationSchedule,
  inferScheduleFromFrequency,
  buildFrequencyFromSchedule,
  isScheduleComplete,
  MedicationScheduleFields,
} from '../utils/medicationSchedule';

interface DiagnosisFormProps {
  onSuccess?: () => void;
}

interface FormData {
  patient_name: string;
  patient_id: string;
  symptoms: string;
  clinical_notes: string;
  diagnosis_text: string;
}

interface Medication extends MedicationScheduleFields {
  id?: number;
  medication_name: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions: string;
}

interface MedicationSafetyAlert {
  severity: 'low' | 'moderate' | 'high';
  medication: string;
  code: string;
  issue: string;
  recommendation: string;
}

interface ExplainabilityEvidence {
  rank: number;
  diagnosis: string;
  supporting_evidence: string[];
  against_evidence: string[];
  missing_data: string[];
}

interface AIAnalysis {
  confidence_score: number;
  suggested_diagnoses: Array<{
    term: string;
    score: number;
  }>;
  active_diagnoses?: string[];
  keywords: string[];
  interpretation: string;
  clinical_reasoning?: string;
  recommendations?: string[];
  medications?: Medication[];
  red_flag_analysis?: {
    has_red_flags: boolean;
    urgency_level: string;
    detected_flags: Array<{
      flag: string;
      keyword: string;
      severity: string;
    }>;
  };
  validator_info?: {
    validator_status: string;
    safety_passed: boolean;
    issues?: string[];
    hallucination_flags?: string[];
  };
  medication_safety?: {
    overall_risk: 'low' | 'moderate' | 'high';
    requires_review: boolean;
    alerts: MedicationSafetyAlert[];
  };
  explainability?: {
    confidence_breakdown?: {
      score: number;
      percent: number;
      drivers: string[];
      uncertainty_factors: string[];
      missing_data: string[];
    };
    diagnosis_evidence?: ExplainabilityEvidence[];
  };
  feedback_loop_info?: {
    used_hints: boolean;
    hint_count: number;
  };
  error?: string;
}

type MedicationField = keyof Omit<Medication, 'id'>;

const DiagnosisForm: React.FC<DiagnosisFormProps> = ({ onSuccess }) => {
  const { notify, confirm } = useFeedback();

  const createMedicationDraft = (): Medication => ({
    id: Date.now() + Math.floor(Math.random() * 1000),
    medication_name: '',
    dosage: '',
    frequency: '',
    ...defaultMedicationSchedule(),
    duration: '',
    instructions: '',
  });

  const [formData, setFormData] = useState<FormData>({
    patient_name: '',
    patient_id: '',
    symptoms: '',
    clinical_notes: '',
    diagnosis_text: '',
  });

  const [aiAnalysis, setAiAnalysis] = useState<AIAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [medications, setMedications] = useState<Medication[]>([]);
  const [streamStatuses, setStreamStatuses] = useState<string[]>([]);
  const [streamedPreview, setStreamedPreview] = useState('');
  const [feedbackNote, setFeedbackNote] = useState('');
  const latestStatus = streamStatuses.length > 0 ? streamStatuses[streamStatuses.length - 1] : '';

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData((prev) => ({
      ...prev,
      [e.target.name]: e.target.value,
    }));
  };

  const removeMedication = (id: number) => {
    setMedications((prev) => prev.filter((med) => med.id !== id));
  };

  const addMedicationRow = () => {
    setMedications((prev) => [...prev, createMedicationDraft()]);
  };

  const updateMedicationField = <K extends MedicationField>(id: number, field: K, value: Medication[K]) => {
    setMedications((prev) =>
      prev.map((med) => (med.id === id ? { ...med, [field]: value } : med))
    );
  };

  const normalizeMedicationKey = (med: Omit<Medication, 'id'>) =>
    `${med.medication_name.trim().toLowerCase()}|${med.dosage.trim().toLowerCase()}|${med.frequency
      .trim()
      .toLowerCase()}|${med.duration.trim().toLowerCase()}|${med.schedule_type}|${med.every_hours || ''}|${
      med.times_per_day || ''
    }|${med.take_morning ? '1' : '0'}${med.take_noon ? '1' : '0'}${med.take_evening ? '1' : '0'}${
      med.take_bedtime ? '1' : '0'
    }${med.take_with_breakfast ? '1' : '0'}${med.take_with_lunch ? '1' : '0'}${
      med.take_with_dinner ? '1' : '0'
    }`;

  const mergeAIMedications = (existing: Medication[], aiMeds: Medication[]) => {
    const existingKeys = new Set(
      existing.map((med) =>
        normalizeMedicationKey({
          medication_name: med.medication_name,
          dosage: med.dosage,
          frequency: med.frequency,
          schedule_type: med.schedule_type,
          every_hours: med.every_hours,
          times_per_day: med.times_per_day,
          take_morning: med.take_morning,
          take_noon: med.take_noon,
          take_evening: med.take_evening,
          take_bedtime: med.take_bedtime,
          take_with_breakfast: med.take_with_breakfast,
          take_with_lunch: med.take_with_lunch,
          take_with_dinner: med.take_with_dinner,
          duration: med.duration,
          instructions: med.instructions,
        })
      )
    );

    const aiDrafts = aiMeds
      .map((med) => {
        const inferredSchedule = inferScheduleFromFrequency(med.frequency || '');
        const schedule = {
          schedule_type: med.schedule_type || inferredSchedule.schedule_type,
          every_hours:
            typeof med.every_hours === 'number' ? med.every_hours : inferredSchedule.every_hours,
          times_per_day:
            typeof med.times_per_day === 'number' ? med.times_per_day : inferredSchedule.times_per_day,
          take_morning: Boolean(
            med.take_morning ?? inferredSchedule.take_morning
          ),
          take_noon: Boolean(
            med.take_noon ?? inferredSchedule.take_noon
          ),
          take_evening: Boolean(
            med.take_evening ?? inferredSchedule.take_evening
          ),
          take_bedtime: Boolean(
            med.take_bedtime ?? inferredSchedule.take_bedtime
          ),
          take_with_breakfast: Boolean(
            med.take_with_breakfast ?? inferredSchedule.take_with_breakfast
          ),
          take_with_lunch: Boolean(
            med.take_with_lunch ?? inferredSchedule.take_with_lunch
          ),
          take_with_dinner: Boolean(
            med.take_with_dinner ?? inferredSchedule.take_with_dinner
          ),
        };

        return {
          id: Date.now() + Math.floor(Math.random() * 1000),
          medication_name: med.medication_name?.trim() || '',
          dosage: med.dosage?.trim() || '',
          frequency: buildFrequencyFromSchedule(schedule, med.frequency?.trim() || ''),
          ...schedule,
          duration: med.duration?.trim() || '',
          instructions: med.instructions?.trim() || '',
        };
      })
      .filter((med) => med.medication_name);

    const uniqueAIMeds = aiDrafts.filter((med) => {
      const key = normalizeMedicationKey({
        medication_name: med.medication_name,
        dosage: med.dosage,
        frequency: med.frequency,
        schedule_type: med.schedule_type,
        every_hours: med.every_hours,
        times_per_day: med.times_per_day,
        take_morning: med.take_morning,
        take_noon: med.take_noon,
        take_evening: med.take_evening,
        take_bedtime: med.take_bedtime,
        take_with_breakfast: med.take_with_breakfast,
        take_with_lunch: med.take_with_lunch,
        take_with_dinner: med.take_with_dinner,
        duration: med.duration,
        instructions: med.instructions,
      });

      if (existingKeys.has(key)) {
        return false;
      }

      existingKeys.add(key);
      return true;
    });

    return [...existing, ...uniqueAIMeds];
  };

  const appendAIMedications = (aiMeds: Medication[]) => {
    if (!aiMeds.length) return;
    const merged = mergeAIMedications(medications, aiMeds);
    const addedCount = merged.length - medications.length;
    if (addedCount > 0) {
      notify(`Auto-filled ${addedCount} AI medication suggestion(s).`, 'info', 2400);
    }
    setMedications(merged);
  };

  const handleAnalyzeSymptoms = async () => {
    if (!formData.symptoms) {
      notify('Please enter symptoms first.', 'warning');
      return;
    }

    setAnalyzing(true);
    setStreamStatuses([]);
    setStreamedPreview('');
    try {
      const payload = await diagnosisAPI.analyzeSymptomsStream(
        {
          symptoms: formData.symptoms,
          clinical_notes: formData.clinical_notes,
        },
        {
          onStatus: (eventPayload) => {
            const message = eventPayload?.message ? String(eventPayload.message) : '';
            if (!message) return;
            setStreamStatuses((prev) => {
              if (prev[prev.length - 1] === message) return prev;
              return [...prev, message];
            });
          },
          onValidation: (eventPayload) => {
            const issues = Array.isArray(eventPayload?.issues) ? eventPayload.issues : [];
            const message =
              issues.length > 0
                ? `Validation: ${issues[0]}`
                : `Validation: ${eventPayload?.safety_passed ? 'Safety checks passed' : 'Safety issues detected'}`;
            setStreamStatuses((prev) => [...prev, message]);
          },
          onToken: (eventPayload) => {
            const tokenText = eventPayload?.text ? String(eventPayload.text) : '';
            if (!tokenText) return;
            setStreamedPreview((prev) => `${prev}${tokenText}`);
          },
          onError: (eventPayload) => {
            const message = eventPayload?.message ? String(eventPayload.message) : 'Stream error';
            setStreamStatuses((prev) => [...prev, message]);
          },
        }
      );

      const analysis = payload?.ai_analysis || null;
      if (analysis) {
        setAiAnalysis(analysis);
        const aiMeds: Medication[] = Array.isArray(analysis?.medications) ? analysis.medications : [];
        appendAIMedications(aiMeds);
      } else {
        throw new Error('Stream completed without analysis payload');
      }
    } catch (error: any) {
      try {
        const response = await diagnosisAPI.analyzeSymptoms({
          symptoms: formData.symptoms,
          clinical_notes: formData.clinical_notes,
        });
        const fallbackAnalysis = response.data;
        setAiAnalysis(fallbackAnalysis);

        const aiMeds: Medication[] = Array.isArray(fallbackAnalysis?.medications)
          ? fallbackAnalysis.medications
          : [];
        appendAIMedications(aiMeds);
        setStreamStatuses((prev) => [...prev, 'Fallback mode used: non-stream analysis completed.']);
      } catch (fallbackError: any) {
        notify(
          `Analysis failed: ${fallbackError.response?.data?.error || fallbackError.message || error.message}`,
          'error'
        );
      }
    } finally {
      setAnalyzing(false);
    }
  };

  const clearFormState = () => {
    setFormData({
      patient_name: '',
      patient_id: '',
      symptoms: '',
      clinical_notes: '',
      diagnosis_text: '',
    });
    setAiAnalysis(null);
    setMedications([]);
    setFeedbackNote('');
  };

  const buildPreparedMedications = () =>
    medications
      .map(({ id, ...med }) => {
        const schedule = {
          schedule_type: med.schedule_type,
          every_hours: med.every_hours ? Number(med.every_hours) : null,
          times_per_day: med.times_per_day ? Number(med.times_per_day) : null,
          take_morning: med.take_morning,
          take_noon: med.take_noon,
          take_evening: med.take_evening,
          take_bedtime: med.take_bedtime,
          take_with_breakfast: med.take_with_breakfast,
          take_with_lunch: med.take_with_lunch,
          take_with_dinner: med.take_with_dinner,
        };

        return {
          medication_name: med.medication_name.trim(),
          dosage: med.dosage.trim(),
          frequency: buildFrequencyFromSchedule(schedule, med.frequency.trim()),
          ...schedule,
          duration: med.duration.trim(),
          instructions: med.instructions.trim(),
        };
      })
      .filter(
        (med) =>
          med.medication_name || med.dosage || med.frequency || med.duration || med.instructions
      );
  
  const hasIncompleteMedication = (preparedMedications: ReturnType<typeof buildPreparedMedications>) =>
    preparedMedications.some(
      (med) =>
        !med.medication_name ||
        !med.dosage ||
        !med.duration ||
        !isScheduleComplete(
          {
            schedule_type: med.schedule_type,
            every_hours: med.every_hours,
            times_per_day: med.times_per_day,
            take_morning: med.take_morning,
            take_noon: med.take_noon,
            take_evening: med.take_evening,
            take_bedtime: med.take_bedtime,
            take_with_breakfast: med.take_with_breakfast,
            take_with_lunch: med.take_with_lunch,
            take_with_dinner: med.take_with_dinner,
          },
          med.frequency
        )
    );

  const saveDiagnosis = async (targetStatus: 'draft' | 'pending') => {
    const patientName = formData.patient_name.trim();
    const patientId = formData.patient_id.trim();
    const symptoms = formData.symptoms.trim();
    const diagnosisText = formData.diagnosis_text.trim();

    if (!patientName || !patientId || !symptoms) {
      notify('Patient name, patient ID, and symptoms are required.', 'warning');
      return;
    }

    if (targetStatus === 'pending' && !diagnosisText) {
      notify('Please enter a final diagnosis before submitting for review.', 'warning');
      return;
    }

    const preparedMedications = buildPreparedMedications();
    if (hasIncompleteMedication(preparedMedications)) {
      notify(
        'Each medication must include name, dosage, duration, and a valid schedule.',
        'warning'
      );
      return;
    }

    setLoading(true);
    try {
      const dataToSubmit = {
        ...formData,
        patient_name: patientName,
        patient_id: patientId,
        symptoms,
        diagnosis_text:
          targetStatus === 'draft'
            ? diagnosisText || 'Draft - pending final diagnosis'
            : diagnosisText,
        ai_prediction: aiAnalysis,
        status: targetStatus,
        medications: preparedMedications,
        feedback_note: feedbackNote.trim(),
      };

      await diagnosisAPI.createDiagnosis(dataToSubmit);

      notify(targetStatus === 'draft' ? 'Draft saved successfully.' : 'Diagnosis submitted for review.', 'success');
      clearFormState();

      if (onSuccess) {
        onSuccess();
      }
    } catch (error: any) {
      notify(`Save failed: ${error.response?.data?.error || error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveDraft = async () => {
    await saveDiagnosis('draft');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await saveDiagnosis('pending');
  };

  return (
    <div className="diagnosis-form-theme max-w-5xl mx-auto px-4">
      <div className="diagnosis-shell-card rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">New Diagnosis</h2>
              <p className="text-xs text-gray-500 mt-0.5">AI-powered clinical decision support</p>
            </div>
            <button
              type="button"
              onClick={async () => {
                const accepted = await confirm({
                  title: 'Clear Form',
                  message: 'Clear all unsaved patient and diagnosis data?',
                  confirmText: 'Clear',
                  cancelText: 'Keep Editing',
                  tone: 'warning',
                });
                if (accepted) {
                  clearFormState();
                  notify('Form cleared.', 'info', 1800);
                }
              }}
              className="ui-btn ui-btn-ghost ui-btn-sm"
            >
              Clear Form
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div>
            <h3 className="text-sm font-medium text-gray-900 mb-3">Patient Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="label">Patient Name *</label>
                <input
                  type="text"
                  name="patient_name"
                  value={formData.patient_name}
                  onChange={handleChange}
                  required
                  className="input-field"
                  placeholder="John Doe"
                />
              </div>
              <div>
                <label className="label">Patient ID *</label>
                <input
                  type="text"
                  name="patient_id"
                  value={formData.patient_id}
                  onChange={handleChange}
                  required
                  className="input-field"
                  placeholder="P12345"
                />
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium text-gray-900 mb-3">Clinical Information</h3>

            <div className="space-y-4">
              <div>
                <label className="label">Symptoms *</label>
                <textarea
                  name="symptoms"
                  value={formData.symptoms}
                  onChange={handleChange}
                  required
                  rows={4}
                  className="input-field resize-none"
                  placeholder="Describe patient symptoms..."
                />
              </div>

              <div>
                <label className="label">Clinical Notes</label>
                <textarea
                  name="clinical_notes"
                  value={formData.clinical_notes}
                  onChange={handleChange}
                  rows={3}
                  className="input-field resize-none"
                  placeholder="Lab results, vitals, exam findings..."
                />
              </div>
            </div>
          </div>

          <div className="flex justify-center py-2">
            <button
              type="button"
              onClick={handleAnalyzeSymptoms}
              disabled={analyzing || !formData.symptoms}
              className="ui-btn ui-btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {analyzing ? 'Analyzing...' : 'Analyze with Med42-v3 AI'}
            </button>
          </div>

          {analyzing && (
            <div className="llm-thinking-wrap">
              <p className="llm-thinking-title">Med42 Is Processing</p>
              <div className="thinking-line">
                <span className="thinking-word">Thinking</span>
                <span className="thinking-dots" aria-hidden="true">
                  <span></span>
                  <span></span>
                  <span></span>
                </span>
              </div>
              <p className="thinking-subtext">Analyzing findings, calibrating risks, and validating safety checks.</p>
              <div className="stream-status-chip">
                {latestStatus || 'Preparing diagnostic reasoning pipeline...'}
              </div>
              {streamedPreview && (
                <div className="stream-preview-panel">
                  <p className="stream-preview-label">Live Draft</p>
                  <p className="stream-preview-text whitespace-pre-wrap line-clamp-6">{streamedPreview}</p>
                </div>
              )}
            </div>
          )}

          {aiAnalysis && !aiAnalysis.error && (
            <div className="border border-blue-200 bg-blue-50 rounded-lg p-4 space-y-4">
              <div className="border-b border-blue-200 pb-3">
                <h3 className="text-sm font-semibold text-gray-900">Med42-v3 Clinical Analysis</h3>
              </div>

              {aiAnalysis.red_flag_analysis?.has_red_flags && (
                <div className="bg-red-50 border border-red-200 rounded p-3">
                  <div className="flex items-start gap-2">
                    <span className="text-red-600 font-semibold text-sm">
                      RED FLAGS - {aiAnalysis.red_flag_analysis.urgency_level}
                    </span>
                  </div>
                  <div className="mt-2 space-y-1">
                    {aiAnalysis.red_flag_analysis.detected_flags.map((flag, idx) => (
                      <div key={idx} className="text-xs text-red-800">
                        - {flag.flag.replace(/_/g, ' ')}: {flag.keyword}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {aiAnalysis.clinical_reasoning && (
                <div className="bg-white border border-gray-200 rounded p-3">
                  <h4 className="text-xs font-semibold text-gray-700 mb-2">Clinical Reasoning</h4>
                  <div className="clinical-content text-xs">{formatAIOutput(aiAnalysis.clinical_reasoning)}</div>
                </div>
              )}

              <div className="bg-white border border-gray-200 rounded p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-gray-700">Confidence</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {formatPercentage(aiAnalysis.confidence_score)}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded h-2">
                  <div
                    className="h-2 rounded bg-blue-600 transition-all"
                    style={{ width: `${safeNumber(aiAnalysis.confidence_score) * 100}%` }}
                  ></div>
                </div>
                {aiAnalysis.interpretation && (
                  <p className="text-xs text-gray-600 mt-2">{aiAnalysis.interpretation}</p>
                )}
              </div>

              {aiAnalysis.keywords && aiAnalysis.keywords.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-700 mb-2">Clinical Features</p>
                  <div className="flex flex-wrap gap-1.5">
                    {aiAnalysis.keywords.map((keyword, index) => (
                      <span
                        key={index}
                        className="px-2 py-1 text-xs bg-purple-100 text-purple-800 rounded border border-purple-200"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {aiAnalysis.suggested_diagnoses && aiAnalysis.suggested_diagnoses.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-700 mb-2">Differential Diagnosis</p>
                  <div className="space-y-2">
                    {aiAnalysis.suggested_diagnoses.map((diag, index) => (
                      <div key={index} className="flex items-center gap-3 bg-white border border-gray-200 rounded p-2">
                        <span
                          className={`w-6 h-6 rounded text-xs font-semibold flex items-center justify-center ${
                            index === 0 ? 'bg-green-600 text-white' : 'bg-blue-600 text-white'
                          }`}
                        >
                          {index + 1}
                        </span>
                        <span className="flex-1 text-xs text-gray-900">{diag.term}</span>
                        <div className="flex items-center gap-2">
                          <div className="w-20 bg-gray-200 rounded h-1.5">
                            <div
                              className={`h-1.5 rounded ${index === 0 ? 'bg-green-600' : 'bg-blue-600'}`}
                              style={{ width: `${safeNumber(diag.score) * 100}%` }}
                            ></div>
                          </div>
                          <span className="text-xs font-medium text-gray-700 w-12 text-right">
                            {formatPercentage(diag.score)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {Array.isArray(aiAnalysis.active_diagnoses) && aiAnalysis.active_diagnoses.length > 1 && (
                <div className="bg-indigo-50 border border-indigo-200 rounded p-3">
                  <p className="text-xs font-semibold text-indigo-900 mb-2">Active Diagnoses (Parallel Management)</p>
                  <ul className="space-y-1">
                    {aiAnalysis.active_diagnoses.map((dx, index) => (
                      <li key={`${dx}-${index}`} className="text-xs text-indigo-800">
                        - {dx}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {aiAnalysis.medications && aiAnalysis.medications.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-700 mb-2">AI-Suggested Medications</p>
                  <p className="text-xs text-gray-500 mb-2">
                    Detected medications are auto-filled in the medication editor below. Review and adjust before saving.
                  </p>
                  <div className="space-y-2">
                    {aiAnalysis.medications.map((med, index) => (
                      <div key={index} className="flex items-start gap-2 bg-white border border-gray-200 rounded p-2">
                        <div className="flex-1">
                          <p className="text-xs font-medium text-gray-900">{med.medication_name}</p>
                          <p className="text-xs text-gray-600 mt-1">
                            {med.dosage} - {med.frequency} - {med.duration}
                          </p>
                        </div>
                        <span className="text-xs px-2 py-1 bg-green-100 text-green-800 rounded border border-green-200">
                          Auto-filled
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {aiAnalysis.recommendations && aiAnalysis.recommendations.length > 0 && (
                <div className="bg-green-50 border border-green-200 rounded p-3">
                  <p className="text-xs font-semibold text-green-900 mb-2">Recommended Workup</p>
                  <ul className="space-y-1">
                    {aiAnalysis.recommendations.map((rec, index) => (
                      <li key={index} className="text-xs text-green-800 flex items-start gap-1">
                        <span>-</span>
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {aiAnalysis.medication_safety && (
                <div
                  className={`rounded p-3 border ${
                    aiAnalysis.medication_safety.overall_risk === 'high'
                      ? 'bg-red-50 border-red-200'
                      : aiAnalysis.medication_safety.overall_risk === 'moderate'
                      ? 'bg-amber-50 border-amber-200'
                      : 'bg-emerald-50 border-emerald-200'
                  }`}
                >
                  <p className="text-xs font-semibold text-gray-900 mb-1">Medication Safety Engine</p>
                  <p className="text-xs text-gray-700">
                    Risk: <span className="font-semibold uppercase">{aiAnalysis.medication_safety.overall_risk}</span>
                    {aiAnalysis.medication_safety.requires_review ? ' (review recommended)' : ' (no major conflicts detected)'}
                  </p>
                  {aiAnalysis.medication_safety.alerts && aiAnalysis.medication_safety.alerts.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {aiAnalysis.medication_safety.alerts.map((alert, index) => (
                        <li key={`${alert.code}-${index}`} className="text-xs text-gray-800">
                          - [{alert.severity.toUpperCase()}] {alert.medication}: {alert.issue} {alert.recommendation}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {aiAnalysis.explainability && (
                <div className="bg-white border border-gray-200 rounded p-3 space-y-3">
                  <p className="text-xs font-semibold text-gray-800">Explainability</p>

                  {aiAnalysis.explainability.confidence_breakdown && (
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-gray-700">Confidence Drivers</p>
                      {aiAnalysis.explainability.confidence_breakdown.drivers?.length ? (
                        <ul className="space-y-1">
                          {aiAnalysis.explainability.confidence_breakdown.drivers.map((item, idx) => (
                            <li key={idx} className="text-xs text-gray-700">- {item}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-gray-600">No specific confidence drivers available.</p>
                      )}

                      {aiAnalysis.explainability.confidence_breakdown.uncertainty_factors?.length > 0 && (
                        <>
                          <p className="text-xs font-medium text-gray-700 pt-1">Uncertainty Factors</p>
                          <ul className="space-y-1">
                            {aiAnalysis.explainability.confidence_breakdown.uncertainty_factors.map((item, idx) => (
                              <li key={idx} className="text-xs text-gray-700">- {item}</li>
                            ))}
                          </ul>
                        </>
                      )}
                    </div>
                  )}

                  {aiAnalysis.explainability.diagnosis_evidence && aiAnalysis.explainability.diagnosis_evidence.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-gray-700">Evidence by Diagnosis</p>
                      {aiAnalysis.explainability.diagnosis_evidence.slice(0, 3).map((item) => (
                        <div key={`${item.rank}-${item.diagnosis}`} className="border border-gray-200 rounded p-2">
                          <p className="text-xs font-semibold text-gray-800">
                            #{item.rank} {item.diagnosis}
                          </p>
                          {item.supporting_evidence?.length > 0 && (
                            <p className="text-xs text-gray-700 mt-1">
                              For: {item.supporting_evidence.join('; ')}
                            </p>
                          )}
                          {item.against_evidence?.length > 0 && (
                            <p className="text-xs text-gray-700 mt-1">
                              Against: {item.against_evidence.join('; ')}
                            </p>
                          )}
                          {item.missing_data?.length > 0 && (
                            <p className="text-xs text-gray-700 mt-1">
                              Missing: {item.missing_data.join('; ')}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {aiAnalysis.feedback_loop_info && (
                <div className="bg-indigo-50 border border-indigo-200 rounded p-3">
                  <p className="text-xs font-semibold text-indigo-900 mb-1">Feedback Learning Loop</p>
                  <p className="text-xs text-indigo-800">
                    {aiAnalysis.feedback_loop_info.used_hints
                      ? `Applied ${aiAnalysis.feedback_loop_info.hint_count} similar doctor correction hint(s) to calibrate this run.`
                      : 'No prior matching doctor corrections were applied for this case.'}
                  </p>
                </div>
              )}

              {aiAnalysis.validator_info && (
                <div className="bg-white border border-gray-200 rounded p-3">
                  <p className="text-xs font-semibold text-gray-800 mb-2">Secondary Validation (watsonx)</p>
                  <p className="text-xs text-gray-700">
                    Status: {aiAnalysis.validator_info.validator_status} | Safety:{' '}
                    {aiAnalysis.validator_info.safety_passed ? 'Passed' : 'Review Required'}
                  </p>
                  {aiAnalysis.validator_info.issues && aiAnalysis.validator_info.issues.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {aiAnalysis.validator_info.issues.map((issue, idx) => (
                        <li key={idx} className="text-xs text-red-700">
                          - {issue}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}

          {aiAnalysis && aiAnalysis.error && (
            <div className="bg-red-50 border border-red-200 rounded p-3">
              <p className="text-xs text-red-800">Error: {aiAnalysis.error}</p>
            </div>
          )}

          <div>
            <label className="label">Final Diagnosis (Required to Submit for Review)</label>
            <textarea
              name="diagnosis_text"
              value={formData.diagnosis_text}
              onChange={handleChange}
              required
              rows={4}
              className="input-field resize-none"
              placeholder="Enter your final clinical diagnosis..."
            />
          </div>

          <div>
            <label className="label">AI Feedback Note (Optional)</label>
            <textarea
              value={feedbackNote}
              onChange={(e) => setFeedbackNote(e.target.value)}
              rows={3}
              className="input-field resize-none"
              placeholder="Why you accepted/changed the AI diagnosis or medications. This helps future calibration."
            />
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-900">
                Medications {medications.length > 0 ? `(${medications.length})` : ''}
              </p>
              <button
                type="button"
                onClick={addMedicationRow}
                className="ui-btn ui-btn-primary ui-btn-sm"
              >
                + Add Medication
              </button>
            </div>

            {medications.length === 0 && (
              <p className="text-xs text-gray-500 border border-dashed border-gray-300 rounded p-3">
                No medications added yet. AI-detected medications will be auto-filled after analysis.
              </p>
            )}

            {medications.map((med, index) => (
              <div key={med.id || index} className="border border-gray-200 rounded p-3 bg-gray-50 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-gray-700">Medication #{index + 1}</p>
                  <button
                    type="button"
                    onClick={() => med.id && removeMedication(med.id)}
                    className="ui-btn ui-btn-danger ui-btn-sm"
                  >
                    Remove
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="label">Medication Name *</label>
                    <input
                      type="text"
                      value={med.medication_name}
                      onChange={(e) => med.id && updateMedicationField(med.id, 'medication_name', e.target.value)}
                      className="input-field"
                      placeholder="e.g. Amoxicillin"
                    />
                  </div>
                  <div>
                    <label className="label">Dosage *</label>
                    <input
                      type="text"
                      value={med.dosage}
                      onChange={(e) => med.id && updateMedicationField(med.id, 'dosage', e.target.value)}
                      className="input-field"
                      placeholder="e.g. 500 mg"
                    />
                  </div>
                  <div>
                    <label className="label">Frequency (summary)</label>
                    <input
                      type="text"
                      value={med.frequency}
                      onChange={(e) => med.id && updateMedicationField(med.id, 'frequency', e.target.value)}
                      className="input-field"
                      placeholder="e.g. Every 8 hours"
                    />
                  </div>
                  <div>
                    <label className="label">Duration *</label>
                    <input
                      type="text"
                      value={med.duration}
                      onChange={(e) => med.id && updateMedicationField(med.id, 'duration', e.target.value)}
                      className="input-field"
                      placeholder="e.g. 7 days"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="label">Schedule Type *</label>
                    <select
                      value={med.schedule_type}
                      onChange={(e) => {
                        if (!med.id) return;
                        const nextType = e.target.value as Medication['schedule_type'];
                        updateMedicationField(med.id, 'schedule_type', nextType);
                        if (nextType !== 'per_hour') updateMedicationField(med.id, 'every_hours', null);
                        if (nextType !== 'per_day') updateMedicationField(med.id, 'times_per_day', null);
                      }}
                      className="input-field"
                    >
                      <option value="free_text">Free text frequency</option>
                      <option value="per_hour">Every X hours</option>
                      <option value="per_day">X times per day</option>
                      <option value="specific_times">Specific times</option>
                    </select>
                  </div>

                  {med.schedule_type === 'per_hour' && (
                    <div>
                      <label className="label">Every (hours) *</label>
                      <input
                        type="number"
                        min={1}
                        value={med.every_hours ?? ''}
                        onChange={(e) =>
                          med.id &&
                          updateMedicationField(
                            med.id,
                            'every_hours',
                            e.target.value ? Number(e.target.value) : null
                          )
                        }
                        className="input-field"
                        placeholder="e.g. 8"
                      />
                    </div>
                  )}

                  {med.schedule_type === 'per_day' && (
                    <div>
                      <label className="label">Times per day *</label>
                      <input
                        type="number"
                        min={1}
                        value={med.times_per_day ?? ''}
                        onChange={(e) =>
                          med.id &&
                          updateMedicationField(
                            med.id,
                            'times_per_day',
                            e.target.value ? Number(e.target.value) : null
                          )
                        }
                        className="input-field"
                        placeholder="e.g. 2"
                      />
                    </div>
                  )}
                </div>

                {med.schedule_type === 'specific_times' && (
                  <div className="border border-gray-200 rounded p-3 bg-white">
                    <p className="text-xs font-medium text-gray-700 mb-2">Select administration times *</p>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                      <label className="text-xs text-gray-700 flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={med.take_morning}
                          onChange={(e) => med.id && updateMedicationField(med.id, 'take_morning', e.target.checked)}
                        />
                        Morning
                      </label>
                      <label className="text-xs text-gray-700 flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={med.take_noon}
                          onChange={(e) => med.id && updateMedicationField(med.id, 'take_noon', e.target.checked)}
                        />
                        Noon
                      </label>
                      <label className="text-xs text-gray-700 flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={med.take_evening}
                          onChange={(e) => med.id && updateMedicationField(med.id, 'take_evening', e.target.checked)}
                        />
                        Evening
                      </label>
                      <label className="text-xs text-gray-700 flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={med.take_bedtime}
                          onChange={(e) => med.id && updateMedicationField(med.id, 'take_bedtime', e.target.checked)}
                        />
                        Bedtime
                      </label>
                      <label className="text-xs text-gray-700 flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={med.take_with_breakfast}
                          onChange={(e) =>
                            med.id && updateMedicationField(med.id, 'take_with_breakfast', e.target.checked)
                          }
                        />
                        With breakfast
                      </label>
                      <label className="text-xs text-gray-700 flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={med.take_with_lunch}
                          onChange={(e) => med.id && updateMedicationField(med.id, 'take_with_lunch', e.target.checked)}
                        />
                        With lunch
                      </label>
                      <label className="text-xs text-gray-700 flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={med.take_with_dinner}
                          onChange={(e) =>
                            med.id && updateMedicationField(med.id, 'take_with_dinner', e.target.checked)
                          }
                        />
                        With dinner
                      </label>
                    </div>
                  </div>
                )}

                <div>
                  <label className="label">Instructions</label>
                  <textarea
                    value={med.instructions}
                    onChange={(e) => med.id && updateMedicationField(med.id, 'instructions', e.target.value)}
                    rows={2}
                    className="input-field resize-none"
                    placeholder="Additional instructions, safety notes, or counseling points..."
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="flex gap-2 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={handleSaveDraft}
              disabled={loading || !formData.patient_name.trim() || !formData.patient_id.trim() || !formData.symptoms.trim()}
              className="ui-btn ui-btn-slate disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Saving...' : 'Save Draft'}
            </button>
            <button
              type="submit"
              disabled={loading || !formData.diagnosis_text.trim()}
              className="ui-btn ui-btn-success disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Saving...' : 'Submit for Review'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DiagnosisForm;
