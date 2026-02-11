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

const DiagnosisForm: React.FC<DiagnosisFormProps> = ({ onSuccess }) => {
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
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const removeMedication = (id: number) => {
    setMedications(medications.filter(med => med.id !== id));
  };

  const addAIMedication = (aiMed: Medication) => {
    setMedications([...medications, { ...aiMed, id: Date.now() }]);
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
      setAiAnalysis(response.data);
    } catch (error: any) {
      alert(`Error: ${error.response?.data?.error || error.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.diagnosis_text) {
      alert('Please enter a final diagnosis');
      return;
    }

    setLoading(true);

    try {
      const dataToSubmit = {
        ...formData,
        ai_prediction: aiAnalysis,
        status: 'pending',
      };
      
      const response = await diagnosisAPI.createDiagnosis(dataToSubmit);
      
      if (medications.length > 0) {
        for (const med of medications) {
          const { id, ...medData } = med;
          await diagnosisAPI.addMedication(response.data.id, medData);
        }
      }
      
      alert('✓ Diagnosis saved successfully');
      
      setFormData({
        patient_name: '',
        patient_id: '',
        symptoms: '',
        clinical_notes: '',
        diagnosis_text: '',
      });
      setAiAnalysis(null);
      setMedications([]);
      
      if (onSuccess) onSuccess();
    } catch (error: any) {
      alert(`Error: ${error.response?.data?.error || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4">
      <div className="bg-white rounded-lg border border-gray-200">
        {/* Header */}
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
          {/* Patient Information */}
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

          {/* Clinical Information */}
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

          {/* AI Analysis Button */}
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

          {/* AI Analysis Results */}
          {aiAnalysis && !aiAnalysis.error && (
            <div className="border border-blue-200 bg-blue-50 rounded-lg p-4 space-y-4">
              <div className="border-b border-blue-200 pb-3">
                <h3 className="text-sm font-semibold text-gray-900">Med42-v3 Clinical Analysis</h3>
              </div>

              {/* Red Flag Alert */}
              {aiAnalysis.red_flag_analysis?.has_red_flags && (
                <div className="bg-red-50 border border-red-200 rounded p-3">
                  <div className="flex items-start gap-2">
                    <span className="text-red-600 font-semibold text-sm">⚠ RED FLAGS - {aiAnalysis.red_flag_analysis.urgency_level}</span>
                  </div>
                  <div className="mt-2 space-y-1">
                    {aiAnalysis.red_flag_analysis.detected_flags.map((flag, idx) => (
                      <div key={idx} className="text-xs text-red-800">
                        • {flag.flag.replace(/_/g, ' ')}: {flag.keyword}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            
              {/* Clinical Reasoning */}
              {aiAnalysis.clinical_reasoning && (
                <div className="bg-white border border-gray-200 rounded p-3">
                  <h4 className="text-xs font-semibold text-gray-700 mb-2">Clinical Reasoning</h4>
                  <div className="clinical-content text-xs">
                    {formatAIOutput(aiAnalysis.clinical_reasoning)}
                  </div>
                </div>
              )}

              {/* Confidence Score */}
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

              {/* Keywords */}
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

              {/* Differential Diagnoses */}
              {aiAnalysis.suggested_diagnoses && aiAnalysis.suggested_diagnoses.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-700 mb-2">Differential Diagnosis</p>
                  <div className="space-y-2">
                    {aiAnalysis.suggested_diagnoses.map((diag, index) => (
                      <div key={index} className="flex items-center gap-3 bg-white border border-gray-200 rounded p-2">
                        <span className={`w-6 h-6 rounded text-xs font-semibold flex items-center justify-center ${index === 0 ? 'bg-green-600 text-white' : 'bg-blue-600 text-white'}`}>
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

              {/* AI-Suggested Medications */}
              {aiAnalysis.medications && aiAnalysis.medications.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-700 mb-2">AI-Suggested Medications</p>
                  <div className="space-y-2">
                    {aiAnalysis.medications.map((med, index) => (
                      <div key={index} className="flex items-start gap-2 bg-white border border-gray-200 rounded p-2">
                        <div className="flex-1">
                          <p className="text-xs font-medium text-gray-900">{med.medication_name}</p>
                          <p className="text-xs text-gray-600 mt-1">
                            {med.dosage} • {med.frequency} • {med.duration}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => addAIMedication(med)}
                          className="text-xs px-2 py-1 bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors"
                        >
                          Add
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {aiAnalysis.recommendations && aiAnalysis.recommendations.length > 0 && (
                <div className="bg-green-50 border border-green-200 rounded p-3">
                  <p className="text-xs font-semibold text-green-900 mb-2">Recommended Workup</p>
                  <ul className="space-y-1">
                    {aiAnalysis.recommendations.map((rec, index) => (
                      <li key={index} className="text-xs text-green-800 flex items-start gap-1">
                        <span>•</span>
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

          {/* Final Diagnosis */}
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

          {/* Medications List */}
          {medications.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-700 mb-2">Medications to Prescribe ({medications.length})</p>
              <div className="space-y-2">
                {medications.map((med) => (
                  <div key={med.id} className="flex items-start gap-2 bg-gray-50 border border-gray-200 rounded p-2">
                    <div className="flex-1">
                      <p className="text-xs font-medium text-gray-900">{med.medication_name}</p>
                      <p className="text-xs text-gray-600 mt-1">
                        {med.dosage} • {med.frequency} • {med.duration}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeMedication(med.id!)}
                      className="text-red-600 hover:text-red-800 text-sm font-bold"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Submit Button */}
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