import React, { useState, useEffect } from 'react';
import { diagnosisAPI } from '../services/api';
import DiagnosisDetail from './DiagnosisDetail';
import { formatPercentage } from '../utils/formatUtils';

interface DiagnosisListProps {
  refreshKey: number;
}

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
  ai_prediction?: any;
  medications?: Array<any>;
  feedback_count?: number;
  latest_feedback_note?: string;
  latest_feedback_summary?: string;
  latest_feedback_at?: string | null;
}

const hasMeaningfulAIAnalysis = (aiPrediction: any): boolean => {
  if (!aiPrediction || typeof aiPrediction !== 'object') return false;
  if (typeof aiPrediction.clinical_reasoning === 'string' && aiPrediction.clinical_reasoning.trim()) return true;
  if (Array.isArray(aiPrediction.suggested_diagnoses) && aiPrediction.suggested_diagnoses.length > 0) return true;
  if (Array.isArray(aiPrediction.active_diagnoses) && aiPrediction.active_diagnoses.length > 0) return true;
  if (Array.isArray(aiPrediction.keywords) && aiPrediction.keywords.length > 0) return true;
  if (Array.isArray(aiPrediction.recommendations) && aiPrediction.recommendations.length > 0) return true;
  if (typeof aiPrediction.confidence_score === 'number' && aiPrediction.confidence_score > 0) return true;
  return false;
};

const DiagnosisList: React.FC<DiagnosisListProps> = ({ refreshKey }) => {
  const [diagnoses, setDiagnoses] = useState<Diagnosis[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDiagnosis, setSelectedDiagnosis] = useState<Diagnosis | null>(null);
  const [filterStatus, setFilterStatus] = useState<'all' | 'draft' | 'pending' | 'approved'>('all');

  useEffect(() => {
    fetchDiagnoses();
  }, [refreshKey]);

  const fetchDiagnoses = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await diagnosisAPI.getAllDiagnoses();
      const diagnosesData = Array.isArray(response.data) ? response.data : [];
      setDiagnoses(diagnosesData);
    } catch (error: any) {
      if (!error.response && error.message === 'Network Error') {
        setError('Network Error: check backend URL/CORS or set REACT_APP_API_BASE_URL.');
      } else {
        setError(error.response?.data?.error || error.message || 'Failed to load diagnoses');
      }
      setDiagnoses([]);
    } finally {
      setLoading(false);
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

  const filteredDiagnoses = filterStatus === 'all' 
    ? diagnoses 
    : diagnoses.filter(d => d.status === filterStatus);

  if (selectedDiagnosis) {
    return (
      <DiagnosisDetail
        diagnosis={selectedDiagnosis}
        onClose={() => {
          setSelectedDiagnosis(null);
          fetchDiagnoses();
        }}
      />
    );
  }

  return (
    <div className="diagnosis-list-theme px-4">
      {/* Filter Tabs */}
      <div className="mb-4 diagnosis-shell-card rounded-lg border border-gray-200 p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setFilterStatus('all')}
              className={`ui-btn ui-btn-sm ${
                filterStatus === 'all'
                  ? 'ui-btn-primary'
                  : 'ui-btn-ghost'
              }`}
            >
              All ({diagnoses.length})
            </button>
            <button
              onClick={() => setFilterStatus('draft')}
              className={`ui-btn ui-btn-sm ${
                filterStatus === 'draft'
                  ? 'ui-btn-slate'
                  : 'ui-btn-ghost'
              }`}
            >
              Draft ({diagnoses.filter(d => d.status === 'draft').length})
            </button>
            <button
              onClick={() => setFilterStatus('pending')}
              className={`ui-btn ui-btn-sm ${
                filterStatus === 'pending'
                  ? 'ui-btn-warning'
                  : 'ui-btn-ghost'
              }`}
            >
              Pending ({diagnoses.filter(d => d.status === 'pending').length})
            </button>
            <button
              onClick={() => setFilterStatus('approved')}
              className={`ui-btn ui-btn-sm ${
                filterStatus === 'approved'
                  ? 'ui-btn-success'
                  : 'ui-btn-ghost'
              }`}
            >
              Approved ({diagnoses.filter(d => d.status === 'approved').length})
            </button>
          </div>
          <button
            onClick={fetchDiagnoses}
            className="ui-btn ui-btn-ghost ui-btn-sm"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded p-3">
          <p className="text-xs text-red-800 mb-2">Error: {error}</p>
          <button
            onClick={fetchDiagnoses}
            className="ui-btn ui-btn-danger ui-btn-sm"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Diagnosis List */}
      {loading ? (
        <div className="flex justify-center items-center py-20">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto"></div>
            <p className="text-xs text-gray-600 mt-3">Loading...</p>
          </div>
        </div>
      ) : filteredDiagnoses.length === 0 ? (
        <div className="diagnosis-shell-card rounded-lg border border-gray-200 p-12 text-center">
          <p className="text-sm text-gray-600">
            {filterStatus === 'all' 
              ? 'No diagnoses found' 
              : `No ${filterStatus} diagnoses found`}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredDiagnoses.map((diagnosis) => (
            <div
              key={diagnosis.id}
              onClick={() => setSelectedDiagnosis(diagnosis)}
              className="bg-white rounded-lg border border-gray-200 hover:border-gray-300 hover:shadow-sm transition-all cursor-pointer"
            >
              <div className="p-4">
                {/* Header */}
                <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <h3 className="text-sm font-semibold text-gray-900">{diagnosis.patient_name}</h3>
                      <span className={`px-2 py-0.5 text-xs font-medium rounded border ${getStatusColor(diagnosis.status)}`}>
                        {diagnosis.status.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-xs text-gray-600">ID: {diagnosis.patient_id}</p>
                  </div>
                  {hasMeaningfulAIAnalysis(diagnosis.ai_prediction) && (
                    <div className="flex items-center gap-1 bg-blue-50 px-2 py-1 rounded border border-blue-200">
                      <span className="text-xs text-blue-700">AI:</span>
                      <span className="text-xs font-semibold text-blue-900">
                        {formatPercentage(diagnosis.ai_prediction.confidence_score)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Content */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-3">
                  <div className="bg-purple-50 border border-purple-200 rounded p-2">
                    <p className="text-xs font-medium text-purple-700 mb-1">Symptoms</p>
                    <p className="text-xs text-gray-800 line-clamp-2">
                      {diagnosis.symptoms}
                    </p>
                  </div>
                  <div className="bg-yellow-50 border border-yellow-200 rounded p-2">
                    <p className="text-xs font-medium text-yellow-700 mb-1">Diagnosis</p>
                    <p className="text-xs text-gray-800 line-clamp-2">
                      {diagnosis.diagnosis_text}
                    </p>
                  </div>
                </div>

                {Array.isArray(diagnosis.ai_prediction?.active_diagnoses) &&
                diagnosis.ai_prediction.active_diagnoses.length > 1 ? (
                  <div className="mb-3 bg-indigo-50 border border-indigo-200 rounded p-2">
                    <p className="text-xs font-medium text-indigo-700 mb-1">Active Diagnoses</p>
                    <div className="flex flex-wrap gap-1.5">
                      {diagnosis.ai_prediction.active_diagnoses.slice(0, 4).map((item: string, idx: number) => (
                        <span
                          key={`${item}-${idx}`}
                          className="px-2 py-0.5 text-xs bg-indigo-100 text-indigo-800 rounded border border-indigo-200"
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}

                {diagnosis.feedback_count ? (
                  <div className="mb-3 bg-amber-50 border border-amber-200 rounded p-2">
                    <p className="text-xs font-medium text-amber-700">
                      AI Feedback Saved ({diagnosis.feedback_count})
                    </p>
                    <p className="text-xs text-gray-700 line-clamp-2">
                      {diagnosis.latest_feedback_note || diagnosis.latest_feedback_summary || 'Doctor feedback captured.'}
                    </p>
                  </div>
                ) : null}

                {/* Footer */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-gray-200">
                  <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                    <span>{diagnosis.doctor_name || 'N/A'}</span>
                    <span>|</span>
                    <span>{new Date(diagnosis.created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {diagnosis.medications && diagnosis.medications.length > 0 && (
                      <span className="bg-purple-100 text-purple-800 px-2 py-0.5 text-xs font-medium rounded border border-purple-200">
                        {diagnosis.medications.length} Med{diagnosis.medications.length !== 1 ? 's' : ''}
                      </span>
                    )}
                    <span className="text-xs text-blue-600 font-medium">View -&gt;</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DiagnosisList;
