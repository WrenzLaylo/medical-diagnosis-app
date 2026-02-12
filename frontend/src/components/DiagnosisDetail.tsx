import React, { useState } from 'react';
import { diagnosisAPI } from '../services/api';
import { formatAIOutput, safeNumber, formatPercentage, getConfidenceGradient } from '../utils/formatUtils';
import { useFeedback } from './ui/FeedbackProvider';
import {
  defaultMedicationSchedule,
  inferScheduleFromFrequency,
  buildFrequencyFromSchedule,
  isScheduleComplete,
  MedicationScheduleFields,
} from '../utils/medicationSchedule';

interface Diagnosis {
  id: number;
  patient_name: string;
  patient_id: string;
  symptoms: string;
  clinical_notes?: string;
  diagnosis_text: string;
  status: 'draft' | 'pending' | 'approved';
  doctor_name?: string;
  created_at: string;
  approved_at?: string;
  ai_prediction?: {
    confidence_score: number;
    suggested_diagnoses?: Array<{
      term: string;
      score: number;
    }>;
    active_diagnoses?: string[];
    keywords?: string[];
    interpretation?: string;
    clinical_reasoning?: string;
    recommendations?: string[];
    red_flag_analysis?: {
      has_red_flags: boolean;
      urgency_level: string;
      detected_flags: Array<{
        flag: string;
        keyword: string;
        severity: string;
      }>;
    };
    medication_safety?: {
      overall_risk: 'low' | 'moderate' | 'high';
      requires_review: boolean;
      alerts?: Array<{
        severity: 'low' | 'moderate' | 'high';
        medication: string;
        code: string;
        issue: string;
        recommendation: string;
      }>;
    };
    explainability?: {
      confidence_breakdown?: {
        score: number;
        percent: number;
        drivers: string[];
        uncertainty_factors: string[];
        missing_data: string[];
      };
      diagnosis_evidence?: Array<{
        rank: number;
        diagnosis: string;
        supporting_evidence: string[];
        against_evidence: string[];
        missing_data: string[];
      }>;
    };
    feedback_loop_info?: {
      used_hints: boolean;
      hint_count: number;
    };
  };
  medications?: Array<{
    id?: number;
    medication_name: string;
    dosage: string;
    frequency: string;
    schedule_type?: MedicationScheduleFields['schedule_type'];
    every_hours?: number | null;
    times_per_day?: number | null;
    take_morning?: boolean;
    take_noon?: boolean;
    take_evening?: boolean;
    take_bedtime?: boolean;
    take_with_breakfast?: boolean;
    take_with_lunch?: boolean;
    take_with_dinner?: boolean;
    duration: string;
    instructions?: string;
  }>;
}

interface DiagnosisDetailProps {
  diagnosis: Diagnosis;
  onClose: () => void;
}

const hasMeaningfulAIAnalysis = (aiPrediction?: Diagnosis['ai_prediction']): boolean => {
  if (!aiPrediction) return false;
  if (typeof aiPrediction.clinical_reasoning === 'string' && aiPrediction.clinical_reasoning.trim()) return true;
  if (Array.isArray(aiPrediction.suggested_diagnoses) && aiPrediction.suggested_diagnoses.length > 0) return true;
  if (Array.isArray(aiPrediction.active_diagnoses) && aiPrediction.active_diagnoses.length > 0) return true;
  if (Array.isArray(aiPrediction.keywords) && aiPrediction.keywords.length > 0) return true;
  if (Array.isArray(aiPrediction.recommendations) && aiPrediction.recommendations.length > 0) return true;
  if (typeof aiPrediction.confidence_score === 'number' && aiPrediction.confidence_score > 0) return true;
  return false;
};

type EditableMedication = {
  id?: number;
  local_id: number;
  medication_name: string;
  dosage: string;
  frequency: string;
  schedule_type: MedicationScheduleFields['schedule_type'];
  every_hours: number | null;
  times_per_day: number | null;
  take_morning: boolean;
  take_noon: boolean;
  take_evening: boolean;
  take_bedtime: boolean;
  take_with_breakfast: boolean;
  take_with_lunch: boolean;
  take_with_dinner: boolean;
  duration: string;
  instructions: string;
};

const createEditableMedication = (): EditableMedication => ({
  local_id: Date.now() + Math.floor(Math.random() * 1000),
  medication_name: '',
  dosage: '',
  frequency: '',
  ...defaultMedicationSchedule(),
  duration: '',
  instructions: '',
});

const mapDiagnosisMedication = (med: NonNullable<Diagnosis['medications']>[number]): EditableMedication => {
  const inferred = inferScheduleFromFrequency(med.frequency || '');
  const schedule = {
    schedule_type: med.schedule_type || inferred.schedule_type,
    every_hours: typeof med.every_hours === 'number' ? med.every_hours : inferred.every_hours,
    times_per_day: typeof med.times_per_day === 'number' ? med.times_per_day : inferred.times_per_day,
    take_morning: Boolean(med.take_morning ?? inferred.take_morning),
    take_noon: Boolean(med.take_noon ?? inferred.take_noon),
    take_evening: Boolean(med.take_evening ?? inferred.take_evening),
    take_bedtime: Boolean(med.take_bedtime ?? inferred.take_bedtime),
    take_with_breakfast: Boolean(med.take_with_breakfast ?? inferred.take_with_breakfast),
    take_with_lunch: Boolean(med.take_with_lunch ?? inferred.take_with_lunch),
    take_with_dinner: Boolean(med.take_with_dinner ?? inferred.take_with_dinner),
  };

  return {
    id: med.id,
    local_id: med.id || Date.now() + Math.floor(Math.random() * 1000),
    medication_name: med.medication_name,
    dosage: med.dosage,
    frequency: buildFrequencyFromSchedule(schedule, med.frequency || ''),
    ...schedule,
    duration: med.duration,
    instructions: med.instructions || '',
  };
};

const DiagnosisDetail: React.FC<DiagnosisDetailProps> = ({ diagnosis, onClose }) => {
  const { notify, confirm } = useFeedback();
  const initialState = {
    diagnosis_text: diagnosis.diagnosis_text,
    clinical_notes: diagnosis.clinical_notes || '',
    medications: (diagnosis.medications || []).map(mapDiagnosisMedication),
  };

  const [isEditing, setIsEditing] = useState(false);
  const [editedDiagnosis, setEditedDiagnosis] = useState(initialState);
  const [feedbackNote, setFeedbackNote] = useState('');
  const [reanalyzing, setReanalyzing] = useState(false);
  const [deletingDraft, setDeletingDraft] = useState(false);
  const hasAISection = hasMeaningfulAIAnalysis(diagnosis.ai_prediction);

  const handleMedicationFieldChange = (
    localId: number,
    field: keyof Omit<EditableMedication, 'id' | 'local_id'>,
    value: EditableMedication[keyof Omit<EditableMedication, 'id' | 'local_id'>]
  ) => {
    setEditedDiagnosis((prev) => ({
      ...prev,
      medications: prev.medications.map((med) =>
        med.local_id === localId ? { ...med, [field]: value } : med
      ),
    }));
  };

  const addMedication = () => {
    setEditedDiagnosis((prev) => ({
      ...prev,
      medications: [...prev.medications, createEditableMedication()],
    }));
  };

  const removeMedication = (localId: number) => {
    setEditedDiagnosis((prev) => ({
      ...prev,
      medications: prev.medications.filter((med) => med.local_id !== localId),
    }));
  };

  const handleCancel = () => {
    setEditedDiagnosis(initialState);
    setFeedbackNote('');
    setIsEditing(false);
  };

  const handleEdit = async () => {
    const medicationsPayload = editedDiagnosis.medications
      .map((med) => {
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
        id: med.id,
        medication_name: med.medication_name.trim(),
        dosage: med.dosage.trim(),
        frequency: buildFrequencyFromSchedule(schedule, med.frequency.trim()),
        ...schedule,
        duration: med.duration.trim(),
        instructions: med.instructions.trim(),
        };
      })
      .filter(
        (med) => med.medication_name || med.dosage || med.frequency || med.duration || med.instructions
      );

    const hasIncompleteMedication = medicationsPayload.some(
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
    if (hasIncompleteMedication) {
      notify('Each medication must include name, dosage, duration, and a valid schedule.', 'warning');
      return;
    }

    try {
      await diagnosisAPI.updateDiagnosis(diagnosis.id, {
        diagnosis_text: editedDiagnosis.diagnosis_text,
        clinical_notes: editedDiagnosis.clinical_notes,
        medications: medicationsPayload,
        feedback_note: feedbackNote.trim(),
      });
      notify('Diagnosis updated successfully.', 'success');
      setFeedbackNote('');
      setIsEditing(false);
      onClose();
    } catch (error: any) {
      console.error('Error updating diagnosis:', error);
      notify(`Error updating diagnosis: ${error.response?.data?.message || error.message}`, 'error');
    }
  };

  const handleApprove = async () => {
    const accepted = await confirm({
      title: 'Approve Diagnosis',
      message: 'Confirm approval of this diagnosis?',
      confirmText: 'Approve',
      cancelText: 'Cancel',
      tone: 'success',
    });
    if (!accepted) return;

    try {
      await diagnosisAPI.approveDiagnosis(diagnosis.id, { feedback_note: feedbackNote.trim() });
      notify('Diagnosis approved successfully.', 'success');
      setFeedbackNote('');
      onClose();
    } catch (error: any) {
      console.error('Error approving diagnosis:', error);
      notify(`Error approving diagnosis: ${error.response?.data?.message || error.message}`, 'error');
    }
  };

  const handleSubmitForReview = async () => {
    const finalDiagnosisText = (isEditing ? editedDiagnosis.diagnosis_text : diagnosis.diagnosis_text).trim();
    const draftPlaceholder = 'draft - pending final diagnosis';
    if (!finalDiagnosisText || finalDiagnosisText.toLowerCase() === draftPlaceholder) {
      notify('Please enter a final diagnosis before submitting draft for review.', 'warning');
      return;
    }

    try {
      await diagnosisAPI.submitForReview(diagnosis.id, { feedback_note: feedbackNote.trim() });
      notify('Draft submitted for review.', 'success');
      setFeedbackNote('');
      onClose();
    } catch (error: any) {
      console.error('Error submitting draft for review:', error);
      notify(`Error submitting draft for review: ${error.response?.data?.message || error.message}`, 'error');
    }
  };

  const handleReanalyzeDraft = async () => {
    if (reanalyzing) return;
    setReanalyzing(true);
    try {
      await diagnosisAPI.reanalyzeDiagnosis(diagnosis.id);
      notify('AI analysis completed. Reopening updated record...', 'success');
      onClose();
    } catch (error: any) {
      console.error('Error reanalyzing diagnosis:', error);
      notify(`AI analysis failed: ${error.response?.data?.message || error.message}`, 'error');
    } finally {
      setReanalyzing(false);
    }
  };

  const handleDeleteDraft = async () => {
    if (diagnosis.status !== 'draft' || deletingDraft) return;
    const accepted = await confirm({
      title: 'Delete Draft',
      message: 'Delete this draft permanently?',
      confirmText: 'Delete',
      cancelText: 'Keep Draft',
      tone: 'error',
    });
    if (!accepted) return;

    setDeletingDraft(true);
    try {
      await diagnosisAPI.deleteDiagnosis(diagnosis.id);
      notify('Draft deleted.', 'success');
      onClose();
    } catch (error: any) {
      console.error('Error deleting draft:', error);
      notify(`Error deleting draft: ${error.response?.data?.message || error.message}`, 'error');
    } finally {
      setDeletingDraft(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved':
        return 'bg-green-100 text-green-800 border-green-300';
      case 'pending':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  return (
    <div className="diagnosis-form-theme max-w-6xl mx-auto px-4 space-y-4">
      <div className="diagnosis-shell-card rounded-lg border border-gray-200 p-4 flex flex-wrap items-center justify-between gap-2">
        <button
          onClick={onClose}
          className="ui-btn ui-btn-ghost"
        >
          Back to List
        </button>

        {diagnosis.status !== 'approved' && !isEditing && (
          <div className="flex gap-2">
            <button
              onClick={handleReanalyzeDraft}
              disabled={reanalyzing}
              className="ui-btn ui-btn-primary disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {reanalyzing ? 'Analyzing...' : 'Run AI Analysis'}
            </button>
            <button
              onClick={() => setIsEditing(true)}
              className="ui-btn ui-btn-primary"
            >
              Edit
            </button>
            {diagnosis.status === 'draft' ? (
              <>
                <button
                  onClick={handleSubmitForReview}
                  className="ui-btn ui-btn-warning"
                >
                  Submit for Review
                </button>
                <button
                  onClick={handleDeleteDraft}
                  disabled={deletingDraft}
                  className="ui-btn ui-btn-danger disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {deletingDraft ? 'Deleting...' : 'Delete Draft'}
                </button>
              </>
            ) : (
              <button
                onClick={handleApprove}
                className="ui-btn ui-btn-success"
              >
                Approve
              </button>
            )}
          </div>
        )}

        {isEditing && (
          <div className="flex gap-2">
            <button
              onClick={handleCancel}
              className="ui-btn ui-btn-ghost"
            >
              Cancel
            </button>
            <button
              onClick={handleEdit}
              className="ui-btn ui-btn-primary"
            >
              Save Changes
            </button>
          </div>
        )}
      </div>

      <div className="diagnosis-shell-card rounded-lg border border-gray-200 overflow-hidden">
        <div className="border-b border-gray-200 px-6 py-4 bg-slate-50">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h1 className="text-xl font-semibold text-gray-900">{diagnosis.patient_name}</h1>
              <p className="text-sm text-gray-600">Patient ID: {diagnosis.patient_id}</p>
            </div>
            <span className={`px-3 py-1 text-xs font-medium border rounded ${getStatusColor(diagnosis.status)}`}>
              {diagnosis.status.toUpperCase()}
            </span>
          </div>
          <div className="mt-3 text-xs text-gray-600">
            <span>{diagnosis.doctor_name || 'N/A'}</span>
            <span className="mx-2">|</span>
            <span>{new Date(diagnosis.created_at).toLocaleString()}</span>
          </div>
        </div>

        <div className="p-6 space-y-6">
          <div className="bg-purple-50 border border-purple-200 rounded p-4">
            <h3 className="text-sm font-semibold text-purple-900 mb-2">Symptoms</h3>
            <p className="text-sm text-gray-800 whitespace-pre-wrap">{diagnosis.symptoms}</p>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded p-4">
            <h3 className="text-sm font-semibold text-blue-900 mb-2">Clinical Notes</h3>
            {isEditing ? (
              <textarea
                value={editedDiagnosis.clinical_notes}
                onChange={(e) =>
                  setEditedDiagnosis((prev) => ({
                    ...prev,
                    clinical_notes: e.target.value,
                  }))
                }
                rows={5}
                className="w-full input-field resize-none"
              />
            ) : (
              <p className="text-sm text-gray-800 whitespace-pre-wrap">{diagnosis.clinical_notes || 'N/A'}</p>
            )}
          </div>

          {!hasAISection && (
            <div className="bg-blue-50 border border-blue-200 rounded p-3">
              <p className="text-xs text-blue-800">
                No AI analysis yet for this record. Use <span className="font-semibold">Run AI Analysis</span> to generate Med42 output.
              </p>
            </div>
          )}

          {hasAISection && diagnosis.ai_prediction && (
            <div className="border border-blue-200 bg-blue-50 rounded-lg p-4 space-y-4">
              <div className="border-b border-blue-200 pb-3">
                <h3 className="text-sm font-semibold text-gray-900">Med42-v3 AI Analysis</h3>
              </div>

              {diagnosis.ai_prediction.clinical_reasoning && (
                <div className="bg-white border border-gray-200 rounded p-3">
                  <h4 className="text-xs font-semibold text-gray-700 mb-2">Clinical Reasoning</h4>
                  <div className="clinical-content text-xs">
                    {formatAIOutput(diagnosis.ai_prediction.clinical_reasoning)}
                  </div>
                </div>
              )}

              <div className="bg-white border border-gray-200 rounded p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-gray-700">Confidence</span>
                  <span className="text-sm font-semibold text-gray-900">
                    {formatPercentage(diagnosis.ai_prediction.confidence_score)}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded h-2">
                  <div
                    className={`h-2 rounded bg-gradient-to-r ${getConfidenceGradient(
                      safeNumber(diagnosis.ai_prediction.confidence_score)
                    )}`}
                    style={{ width: `${safeNumber(diagnosis.ai_prediction.confidence_score) * 100}%` }}
                  ></div>
                </div>
                {diagnosis.ai_prediction.interpretation && (
                  <p className="text-xs text-gray-600 mt-2">{diagnosis.ai_prediction.interpretation}</p>
                )}
              </div>

              {diagnosis.ai_prediction.keywords && diagnosis.ai_prediction.keywords.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-700 mb-2">Clinical Features</p>
                  <div className="flex flex-wrap gap-1.5">
                    {diagnosis.ai_prediction.keywords.map((keyword, index) => (
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

              {diagnosis.ai_prediction.suggested_diagnoses && (
                <div>
                  <p className="text-xs font-medium text-gray-700 mb-2">Differential Diagnosis</p>
                  <div className="space-y-2">
                    {diagnosis.ai_prediction.suggested_diagnoses.map((diag, index) => (
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

              {Array.isArray(diagnosis.ai_prediction.active_diagnoses) &&
                diagnosis.ai_prediction.active_diagnoses.length > 1 && (
                  <div className="bg-indigo-50 border border-indigo-200 rounded p-3">
                    <p className="text-xs font-semibold text-indigo-900 mb-2">Active Diagnoses (Parallel Management)</p>
                    <ul className="space-y-1">
                      {diagnosis.ai_prediction.active_diagnoses.map((dx, index) => (
                        <li key={`${dx}-${index}`} className="text-xs text-indigo-800">
                          - {dx}
                        </li>
                      ))}
                    </ul>
                  </div>
              )}

              {diagnosis.ai_prediction.recommendations && diagnosis.ai_prediction.recommendations.length > 0 && (
                <div className="bg-green-50 border border-green-200 rounded p-3">
                  <p className="text-xs font-semibold text-green-900 mb-2">Recommended Workup</p>
                  <ul className="space-y-1">
                    {diagnosis.ai_prediction.recommendations.map((rec, index) => (
                      <li key={index} className="text-xs text-green-800 flex items-start gap-1">
                        <span>-</span>
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {diagnosis.ai_prediction.medication_safety && (
                <div
                  className={`rounded p-3 border ${
                    diagnosis.ai_prediction.medication_safety.overall_risk === 'high'
                      ? 'bg-red-50 border-red-200'
                      : diagnosis.ai_prediction.medication_safety.overall_risk === 'moderate'
                      ? 'bg-amber-50 border-amber-200'
                      : 'bg-emerald-50 border-emerald-200'
                  }`}
                >
                  <p className="text-xs font-semibold text-gray-900 mb-1">Medication Safety Engine</p>
                  <p className="text-xs text-gray-700">
                    Risk:{' '}
                    <span className="font-semibold uppercase">
                      {diagnosis.ai_prediction.medication_safety.overall_risk}
                    </span>
                    {diagnosis.ai_prediction.medication_safety.requires_review
                      ? ' (review recommended)'
                      : ' (no major conflicts detected)'}
                  </p>
                  {diagnosis.ai_prediction.medication_safety.alerts &&
                    diagnosis.ai_prediction.medication_safety.alerts.length > 0 && (
                      <ul className="mt-2 space-y-1">
                        {diagnosis.ai_prediction.medication_safety.alerts.map((alert, idx) => (
                          <li key={`${alert.code}-${idx}`} className="text-xs text-gray-800">
                            - [{alert.severity.toUpperCase()}] {alert.medication}: {alert.issue} {alert.recommendation}
                          </li>
                        ))}
                      </ul>
                    )}
                </div>
              )}

              {diagnosis.ai_prediction.explainability && (
                <div className="bg-white border border-gray-200 rounded p-3 space-y-3">
                  <p className="text-xs font-semibold text-gray-800">Explainability</p>
                  {(diagnosis.ai_prediction.explainability.confidence_breakdown?.drivers?.length ?? 0) > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-700 mb-1">Confidence Drivers</p>
                      <ul className="space-y-1">
                        {(diagnosis.ai_prediction.explainability.confidence_breakdown?.drivers || []).map((driver, idx) => (
                          <li key={idx} className="text-xs text-gray-700">- {driver}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {(diagnosis.ai_prediction.explainability.confidence_breakdown?.uncertainty_factors?.length ?? 0) > 0 && (
                    <div>
                      <p className="text-xs font-medium text-gray-700 mb-1">Uncertainty Factors</p>
                      <ul className="space-y-1">
                        {(diagnosis.ai_prediction.explainability.confidence_breakdown?.uncertainty_factors || []).map((item, idx) => (
                          <li key={idx} className="text-xs text-gray-700">- {item}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {diagnosis.ai_prediction.feedback_loop_info && (
                <div className="bg-indigo-50 border border-indigo-200 rounded p-3">
                  <p className="text-xs font-semibold text-indigo-900 mb-1">Feedback Learning Loop</p>
                  <p className="text-xs text-indigo-800">
                    {diagnosis.ai_prediction.feedback_loop_info.used_hints
                      ? `Applied ${diagnosis.ai_prediction.feedback_loop_info.hint_count} similar doctor correction hint(s) for this case.`
                      : 'No prior matching doctor corrections were applied for this case.'}
                  </p>
                </div>
              )}
            </div>
          )}

          <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
            <h3 className="text-sm font-semibold text-yellow-900 mb-2">Final Diagnosis</h3>
            {isEditing ? (
              <textarea
                value={editedDiagnosis.diagnosis_text}
                onChange={(e) =>
                  setEditedDiagnosis((prev) => ({
                    ...prev,
                    diagnosis_text: e.target.value,
                  }))
                }
                rows={5}
                className="w-full input-field resize-none"
              />
            ) : (
              <p className="text-sm text-gray-800 whitespace-pre-wrap">{diagnosis.diagnosis_text}</p>
            )}
          </div>

          {(isEditing || diagnosis.status !== 'approved') && (
            <div className="bg-white border border-gray-200 rounded p-4">
              <label className="label">AI Feedback Note (Optional)</label>
              <textarea
                value={feedbackNote}
                onChange={(e) => setFeedbackNote(e.target.value)}
                rows={3}
                className="w-full input-field resize-none"
                placeholder="Why you accepted/changed the AI diagnosis or medications. This feeds future calibration."
              />
            </div>
          )}

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">
                Medications {isEditing ? `(${editedDiagnosis.medications.length})` : `(${diagnosis.medications?.length || 0})`}
              </h3>
              {isEditing && (
                <button
                  type="button"
                  onClick={addMedication}
                  className="ui-btn ui-btn-primary ui-btn-sm"
                >
                  + Add Medication
                </button>
              )}
            </div>

            {!isEditing && (!diagnosis.medications || diagnosis.medications.length === 0) && (
              <p className="text-xs text-gray-500 border border-dashed border-gray-300 rounded p-3">
                No medications recorded.
              </p>
            )}

            {isEditing
              ? editedDiagnosis.medications.map((med, index) => (
                  <div key={med.local_id} className="border border-gray-200 rounded p-3 bg-gray-50 space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-gray-700">Medication #{index + 1}</p>
                      <button
                        type="button"
                        onClick={() => removeMedication(med.local_id)}
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
                          onChange={(e) =>
                            handleMedicationFieldChange(med.local_id, 'medication_name', e.target.value)
                          }
                          className="input-field"
                          placeholder="e.g. Amoxicillin"
                        />
                      </div>
                      <div>
                        <label className="label">Dosage *</label>
                        <input
                          type="text"
                          value={med.dosage}
                          onChange={(e) => handleMedicationFieldChange(med.local_id, 'dosage', e.target.value)}
                          className="input-field"
                          placeholder="e.g. 500 mg"
                        />
                      </div>
                      <div>
                        <label className="label">Frequency (summary)</label>
                        <input
                          type="text"
                          value={med.frequency}
                          onChange={(e) => handleMedicationFieldChange(med.local_id, 'frequency', e.target.value)}
                          className="input-field"
                          placeholder="e.g. Every 8 hours"
                        />
                      </div>
                      <div>
                        <label className="label">Duration *</label>
                        <input
                          type="text"
                          value={med.duration}
                          onChange={(e) => handleMedicationFieldChange(med.local_id, 'duration', e.target.value)}
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
                            const nextType = e.target.value as EditableMedication['schedule_type'];
                            handleMedicationFieldChange(med.local_id, 'schedule_type', nextType);
                            if (nextType !== 'per_hour') handleMedicationFieldChange(med.local_id, 'every_hours', null);
                            if (nextType !== 'per_day') handleMedicationFieldChange(med.local_id, 'times_per_day', null);
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
                              handleMedicationFieldChange(
                                med.local_id,
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
                              handleMedicationFieldChange(
                                med.local_id,
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
                              onChange={(e) => handleMedicationFieldChange(med.local_id, 'take_morning', e.target.checked)}
                            />
                            Morning
                          </label>
                          <label className="text-xs text-gray-700 flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={med.take_noon}
                              onChange={(e) => handleMedicationFieldChange(med.local_id, 'take_noon', e.target.checked)}
                            />
                            Noon
                          </label>
                          <label className="text-xs text-gray-700 flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={med.take_evening}
                              onChange={(e) =>
                                handleMedicationFieldChange(med.local_id, 'take_evening', e.target.checked)
                              }
                            />
                            Evening
                          </label>
                          <label className="text-xs text-gray-700 flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={med.take_bedtime}
                              onChange={(e) =>
                                handleMedicationFieldChange(med.local_id, 'take_bedtime', e.target.checked)
                              }
                            />
                            Bedtime
                          </label>
                          <label className="text-xs text-gray-700 flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={med.take_with_breakfast}
                              onChange={(e) =>
                                handleMedicationFieldChange(
                                  med.local_id,
                                  'take_with_breakfast',
                                  e.target.checked
                                )
                              }
                            />
                            With breakfast
                          </label>
                          <label className="text-xs text-gray-700 flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={med.take_with_lunch}
                              onChange={(e) =>
                                handleMedicationFieldChange(med.local_id, 'take_with_lunch', e.target.checked)
                              }
                            />
                            With lunch
                          </label>
                          <label className="text-xs text-gray-700 flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={med.take_with_dinner}
                              onChange={(e) =>
                                handleMedicationFieldChange(med.local_id, 'take_with_dinner', e.target.checked)
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
                        onChange={(e) => handleMedicationFieldChange(med.local_id, 'instructions', e.target.value)}
                        rows={2}
                        className="input-field resize-none"
                        placeholder="Additional instructions, safety notes, or counseling points..."
                      />
                    </div>
                  </div>
                ))
              : diagnosis.medications?.map((med) => (
                  <div key={med.id} className="border border-gray-200 rounded p-3 bg-gray-50">
                    <p className="text-sm font-semibold text-gray-900">{med.medication_name}</p>
                    <p className="text-xs text-gray-700 mt-1">
                      {med.dosage} - {med.frequency} - {med.duration}
                    </p>
                    {med.instructions && <p className="text-xs text-gray-600 mt-2">{med.instructions}</p>}
                  </div>
                ))}
          </div>

          {diagnosis.approved_at && (
            <div className="bg-green-50 border border-green-200 rounded p-3">
              <p className="text-sm text-green-800">
                Approved: {new Date(diagnosis.approved_at).toLocaleString()}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DiagnosisDetail;
