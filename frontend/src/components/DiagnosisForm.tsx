import React, { useState } from 'react';
import { diagnosisAPI } from '../services/api';
import { formatAIOutput, safeNumber, formatPercentage } from '../utils/formatUtils';

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

interface Medication {
  id?: number;
  medication_name: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions: string;
}

interface AIAnalysis {
  confidence_score: number;
  suggested_diagnoses: Array<{
    term: string;
    score: number;
  }>;
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
  error?: string;
}

type MedicationField = keyof Omit<Medication, 'id'>;

const DiagnosisForm: React.FC<DiagnosisFormProps> = ({ onSuccess }) => {
  const createMedicationDraft = (): Medication => ({
    id: Date.now() + Math.floor(Math.random() * 1000),
    medication_name: '',
    dosage: '',
    frequency: '',
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

  const updateMedicationField = (id: number, field: MedicationField, value: string) => {
    setMedications((prev) =>
      prev.map((med) => (med.id === id ? { ...med, [field]: value } : med))
    );
  };

  const normalizeMedicationKey = (med: Omit<Medication, 'id'>) =>
    `${med.medication_name.trim().toLowerCase()}|${med.dosage.trim().toLowerCase()}|${med.frequency
      .trim()
      .toLowerCase()}|${med.duration.trim().toLowerCase()}`;

  const mergeAIMedications = (existing: Medication[], aiMeds: Medication[]) => {
    const existingKeys = new Set(
      existing.map((med) =>
        normalizeMedicationKey({
          medication_name: med.medication_name,
          dosage: med.dosage,
          frequency: med.frequency,
          duration: med.duration,
          instructions: med.instructions,
        })
      )
    );

    const aiDrafts = aiMeds
      .map((med) => ({
        id: Date.now() + Math.floor(Math.random() * 1000),
        medication_name: med.medication_name?.trim() || '',
        dosage: med.dosage?.trim() || '',
        frequency: med.frequency?.trim() || '',
        duration: med.duration?.trim() || '',
        instructions: med.instructions?.trim() || '',
      }))
      .filter((med) => med.medication_name);

    const uniqueAIMeds = aiDrafts.filter((med) => {
      const key = normalizeMedicationKey({
        medication_name: med.medication_name,
        dosage: med.dosage,
        frequency: med.frequency,
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

  const handleAnalyzeSymptoms = async () => {
    if (!formData.symptoms) {
      alert('Please enter symptoms first');
      return;
    }

    setAnalyzing(true);
    try {
      const response = await diagnosisAPI.analyzeSymptoms({
        symptoms: formData.symptoms,
        clinical_notes: formData.clinical_notes,
      });

      const analysis = response.data;
      setAiAnalysis(analysis);

      const aiMeds: Medication[] = Array.isArray(analysis?.medications) ? analysis.medications : [];
      if (aiMeds.length > 0) {
        setMedications((prev) => mergeAIMedications(prev, aiMeds));
      }
    } catch (error: any) {
      alert(`Error: ${error.response?.data?.error || error.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.diagnosis_text.trim()) {
      alert('Please enter a final diagnosis');
      return;
    }

    const preparedMedications = medications
      .map(({ id, ...med }) => ({
        medication_name: med.medication_name.trim(),
        dosage: med.dosage.trim(),
        frequency: med.frequency.trim(),
        duration: med.duration.trim(),
        instructions: med.instructions.trim(),
      }))
      .filter((med) => med.medication_name || med.dosage || med.frequency || med.duration || med.instructions);

    const hasIncompleteMedication = preparedMedications.some(
      (med) => !med.medication_name || !med.dosage || !med.frequency || !med.duration
    );
    if (hasIncompleteMedication) {
      alert('Each medication must include name, dosage, frequency, and duration.');
      return;
    }

    setLoading(true);
    try {
      const dataToSubmit = {
        ...formData,
        ai_prediction: aiAnalysis,
        status: 'pending',
        medications: preparedMedications,
      };

      await diagnosisAPI.createDiagnosis(dataToSubmit);

      alert('Diagnosis saved successfully');

      setFormData({
        patient_name: '',
        patient_id: '',
        symptoms: '',
        clinical_notes: '',
        diagnosis_text: '',
      });
      setAiAnalysis(null);
      setMedications([]);

      if (onSuccess) {
        onSuccess();
      }
    } catch (error: any) {
      alert(`Error: ${error.response?.data?.error || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4">
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">New Diagnosis</h2>
              <p className="text-xs text-gray-500 mt-0.5">AI-powered clinical decision support</p>
            </div>
            <button
              type="button"
              onClick={() => {
                if (window.confirm('Clear all form data?')) {
                  setFormData({
                    patient_name: '',
                    patient_id: '',
                    symptoms: '',
                    clinical_notes: '',
                    diagnosis_text: '',
                  });
                  setAiAnalysis(null);
                  setMedications([]);
                }
              }}
              className="text-xs text-gray-600 hover:text-gray-900 px-3 py-1.5 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
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
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {analyzing ? 'Analyzing...' : 'Analyze with Med42-v3 AI'}
            </button>
          </div>

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
            </div>
          )}

          {aiAnalysis && aiAnalysis.error && (
            <div className="bg-red-50 border border-red-200 rounded p-3">
              <p className="text-xs text-red-800">Error: {aiAnalysis.error}</p>
            </div>
          )}

          <div>
            <label className="label">Final Diagnosis *</label>
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

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-gray-900">
                Medications {medications.length > 0 ? `(${medications.length})` : ''}
              </p>
              <button
                type="button"
                onClick={addMedicationRow}
                className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
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
                    <label className="label">Frequency *</label>
                    <input
                      type="text"
                      value={med.frequency}
                      onChange={(e) => med.id && updateMedicationField(med.id, 'frequency', e.target.value)}
                      className="input-field"
                      placeholder="e.g. PO every 8 hours"
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
              type="submit"
              disabled={loading || !formData.diagnosis_text}
              className="btn-success disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Saving...' : 'Save Diagnosis'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DiagnosisForm;
