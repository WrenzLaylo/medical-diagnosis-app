import React, { useState } from 'react';
import { diagnosisAPI } from '../services/api';
import { formatAIOutput, safeNumber, formatPercentage, getConfidenceGradient } from '../utils/formatUtils';

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
  };
  medications?: Array<{
    id?: number;
    medication_name: string;
    dosage: string;
    frequency: string;
    duration: string;
    instructions?: string;
  }>;
}

interface DiagnosisDetailProps {
  diagnosis: Diagnosis;
  onClose: () => void;
}

type EditableMedication = {
  id?: number;
  local_id: number;
  medication_name: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions: string;
};

const createEditableMedication = (): EditableMedication => ({
  local_id: Date.now() + Math.floor(Math.random() * 1000),
  medication_name: '',
  dosage: '',
  frequency: '',
  duration: '',
  instructions: '',
});

const mapDiagnosisMedication = (med: NonNullable<Diagnosis['medications']>[number]): EditableMedication => ({
  id: med.id,
  local_id: med.id || Date.now() + Math.floor(Math.random() * 1000),
  medication_name: med.medication_name,
  dosage: med.dosage,
  frequency: med.frequency,
  duration: med.duration,
  instructions: med.instructions || '',
});

const DiagnosisDetail: React.FC<DiagnosisDetailProps> = ({ diagnosis, onClose }) => {
  const initialState = {
    diagnosis_text: diagnosis.diagnosis_text,
    clinical_notes: diagnosis.clinical_notes || '',
    medications: (diagnosis.medications || []).map(mapDiagnosisMedication),
  };

  const [isEditing, setIsEditing] = useState(false);
  const [editedDiagnosis, setEditedDiagnosis] = useState(initialState);

  const handleMedicationFieldChange = (
    localId: number,
    field: keyof Omit<EditableMedication, 'id' | 'local_id'>,
    value: string
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
    setIsEditing(false);
  };

  const handleEdit = async () => {
    const medicationsPayload = editedDiagnosis.medications
      .map((med) => ({
        id: med.id,
        medication_name: med.medication_name.trim(),
        dosage: med.dosage.trim(),
        frequency: med.frequency.trim(),
        duration: med.duration.trim(),
        instructions: med.instructions.trim(),
      }))
      .filter((med) => med.medication_name || med.dosage || med.frequency || med.duration || med.instructions);

    const hasIncompleteMedication = medicationsPayload.some(
      (med) => !med.medication_name || !med.dosage || !med.frequency || !med.duration
    );
    if (hasIncompleteMedication) {
      alert('Each medication must include name, dosage, frequency, and duration.');
      return;
    }

    try {
      await diagnosisAPI.updateDiagnosis(diagnosis.id, {
        diagnosis_text: editedDiagnosis.diagnosis_text,
        clinical_notes: editedDiagnosis.clinical_notes,
        medications: medicationsPayload,
      });
      alert('Diagnosis updated successfully');
      setIsEditing(false);
      onClose();
    } catch (error) {
      console.error('Error updating diagnosis:', error);
      alert('Error updating diagnosis.');
    }
  };

  const handleApprove = async () => {
    if (window.confirm('Are you sure you want to approve this diagnosis?')) {
      try {
        await diagnosisAPI.approveDiagnosis(diagnosis.id);
        alert('Diagnosis approved successfully');
        onClose();
      } catch (error) {
        console.error('Error approving diagnosis:', error);
        alert('Error approving diagnosis.');
      }
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
    <div className="max-w-6xl mx-auto px-4 space-y-4">
      <div className="bg-white rounded-lg border border-gray-200 p-4 flex flex-wrap items-center justify-between gap-2">
        <button
          onClick={onClose}
          className="px-4 py-2 text-sm border border-gray-300 rounded hover:bg-gray-50 transition-colors"
        >
          Back to List
        </button>

        {diagnosis.status !== 'approved' && !isEditing && (
          <div className="flex gap-2">
            <button
              onClick={() => setIsEditing(true)}
              className="px-4 py-2 text-sm border border-blue-300 text-blue-700 rounded hover:bg-blue-50 transition-colors"
            >
              Edit
            </button>
            <button
              onClick={handleApprove}
              className="px-4 py-2 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
            >
              Approve
            </button>
          </div>
        )}

        {isEditing && (
          <div className="flex gap-2">
            <button
              onClick={handleCancel}
              className="px-4 py-2 text-sm border border-gray-300 rounded hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleEdit}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              Save Changes
            </button>
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
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

          {diagnosis.ai_prediction && (
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

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">
                Medications {isEditing ? `(${editedDiagnosis.medications.length})` : `(${diagnosis.medications?.length || 0})`}
              </h3>
              {isEditing && (
                <button
                  type="button"
                  onClick={addMedication}
                  className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
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
                        className="text-xs px-2 py-1 border border-red-200 text-red-700 rounded hover:bg-red-50 transition-colors"
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
                        <label className="label">Frequency *</label>
                        <input
                          type="text"
                          value={med.frequency}
                          onChange={(e) => handleMedicationFieldChange(med.local_id, 'frequency', e.target.value)}
                          className="input-field"
                          placeholder="e.g. PO every 8 hours"
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
