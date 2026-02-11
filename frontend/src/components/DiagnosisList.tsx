import React, { useState, useEffect } from 'react';
import { diagnosisAPI } from '../services/api';
import DiagnosisDetail from './DiagnosisDetail';
import { safeNumber, formatPercentage } from '../utils/formatUtils';

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
}

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
      setError(error.response?.data?.error || error.message || 'Failed to load diagnoses');
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
    <div className="px-4">
      {/* Filter Tabs */}
      <div className="mb-4 bg-white rounded-lg border border-gray-200 p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setFilterStatus('all')}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                filterStatus === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
              }`}
            >
              All ({diagnoses.length})
            </button>
            <button
              onClick={() => setFilterStatus('draft')}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                filterStatus === 'draft'
                  ? 'bg-gray-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
              }`}
            >
              Draft ({diagnoses.filter(d => d.status === 'draft').length})
            </button>
            <button
              onClick={() => setFilterStatus('pending')}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                filterStatus === 'pending'
                  ? 'bg-yellow-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
              }`}
            >
              Pending ({diagnoses.filter(d => d.status === 'pending').length})
            </button>
            <button
              onClick={() => setFilterStatus('approved')}
              className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                filterStatus === 'approved'
                  ? 'bg-green-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
              }`}
            >
              Approved ({diagnoses.filter(d => d.status === 'approved').length})
            </button>
          </div>
          <button
            onClick={fetchDiagnoses}
            className="px-3 py-1.5 text-xs font-medium text-gray-700 border border-gray-300 rounded hover:bg-gray-50 transition-colors"
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
            className="text-xs px-3 py-1.5 bg-red-600 text-white rounded hover:bg-red-700 transition-colors"
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
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
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
                  {diagnosis.ai_prediction && (
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

                {/* Footer */}
                <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-gray-200">
                  <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                    <span>{diagnosis.doctor_name || 'N/A'}</span>
                    <span>•</span>
                    <span>{new Date(diagnosis.created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {diagnosis.medications && diagnosis.medications.length > 0 && (
                      <span className="bg-purple-100 text-purple-800 px-2 py-0.5 text-xs font-medium rounded border border-purple-200">
                        {diagnosis.medications.length} Med{diagnosis.medications.length !== 1 ? 's' : ''}
                      </span>
                    )}
                    <span className="text-xs text-blue-600 font-medium">View →</span>
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