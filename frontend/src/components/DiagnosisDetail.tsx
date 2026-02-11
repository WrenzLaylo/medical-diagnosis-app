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
    id: number;
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

const DiagnosisDetail: React.FC<DiagnosisDetailProps> = ({ diagnosis, onClose }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedDiagnosis, setEditedDiagnosis] = useState({
    diagnosis_text: diagnosis.diagnosis_text,
    clinical_notes: diagnosis.clinical_notes || '',
  });

  const handleEdit = async () => {
    try {
      await diagnosisAPI.updateDiagnosis(diagnosis.id, editedDiagnosis);
      alert('✓ Diagnosis updated successfully!');
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
        alert('✓ Diagnosis approved successfully!');
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
        return 'bg-gradient-to-r from-green-100 to-green-200 text-green-800 border-green-400';
      case 'pending':
        return 'bg-gradient-to-r from-yellow-100 to-yellow-200 text-yellow-800 border-yellow-400';
      default:
        return 'bg-gradient-to-r from-gray-100 to-gray-200 text-gray-800 border-gray-400';
    }
  };

  const getUrgencyColor = (level: string) => {
    switch (level) {
      case 'URGENT':
        return 'bg-red-50 border-red-400 shadow-red-100';
      case 'HIGH':
        return 'bg-orange-50 border-orange-400 shadow-orange-100';
      default:
        return 'bg-green-50 border-green-400 shadow-green-100';
    }
  };

  const getUrgencyTextColor = (level: string) => {
    switch (level) {
      case 'URGENT':
        return 'text-red-900';
      case 'HIGH':
        return 'text-orange-900';
      default:
        return 'text-green-900';
    }
  };

  return (
    <div className="max-w-6xl mx-auto animate-fadeIn">
      {/* Action Bar */}
      <div className="mb-6 flex flex-col sm:flex-row items-center justify-between gap-4 bg-white rounded-xl shadow-lg p-4">
        <button
          onClick={onClose}
          className="group px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-lg transition-all duration-200 flex items-center shadow-md hover:shadow-lg transform hover:scale-105 active:scale-95"
        >
          <span className="mr-2 group-hover:-translate-x-1 transition-transform duration-200">←</span>
          Back to List
        </button>
        
        {diagnosis.status !== 'approved' && !isEditing && (
          <div className="flex gap-3">
            <button
              onClick={() => setIsEditing(true)}
              className="group px-6 py-3 bg-blue-100 hover:bg-blue-200 text-blue-700 font-semibold rounded-lg transition-all duration-200 flex items-center shadow-md hover:shadow-lg transform hover:scale-105 active:scale-95"
            >
              <span className="mr-2 group-hover:rotate-12 transition-transform duration-200">✏️</span>
              Edit
            </button>
            <button
              onClick={handleApprove}
              className="group px-6 py-3 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-700 hover:to-emerald-700 text-white font-semibold rounded-lg transition-all duration-200 flex items-center shadow-md hover:shadow-lg transform hover:scale-105 active:scale-95"
            >
              <span className="mr-2 group-hover:scale-110 transition-transform duration-200">✓</span>
              Approve
            </button>
          </div>
        )}
        
        {isEditing && (
          <div className="flex gap-3">
            <button
              onClick={() => setIsEditing(false)}
              className="px-6 py-3 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-lg transition-all duration-200 shadow-md hover:shadow-lg transform hover:scale-105 active:scale-95"
            >
              Cancel
            </button>
            <button
              onClick={handleEdit}
              className="group px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold rounded-lg transition-all duration-200 flex items-center shadow-md hover:shadow-lg transform hover:scale-105 active:scale-95"
            >
              <span className="mr-2 group-hover:animate-bounce">💾</span>
              Save Changes
            </button>
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-8 py-6">
          <div className="flex flex-col sm:flex-row justify-between items-start gap-4">
            <div className="flex-1">
              <h1 className="text-4xl font-bold text-white mb-3 flex items-center">
                <span className="mr-3">👤</span>
                {diagnosis.patient_name}
              </h1>
              <p className="text-lg text-blue-100 font-semibold">Patient ID: {diagnosis.patient_id}</p>
            </div>
            <span className={`px-6 py-3 rounded-full text-base font-bold border-4 shadow-lg ${getStatusColor(diagnosis.status)}`}>
              {diagnosis.status.toUpperCase()}
            </span>
          </div>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-6">
            <div className="flex items-center bg-white bg-opacity-20 backdrop-blur-sm p-4 rounded-lg">
              <span className="text-blue-100 font-semibold mr-2">👨‍⚕️ Doctor:</span>
              <span className="font-bold text-white">{diagnosis.doctor_name || 'N/A'}</span>
            </div>
            <div className="flex items-center bg-white bg-opacity-20 backdrop-blur-sm p-4 rounded-lg">
              <span className="text-blue-100 font-semibold mr-2">📅 Created:</span>
              <span className="font-bold text-white">
                {new Date(diagnosis.created_at).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        <div className="p-8 space-y-6">
          {/* Symptoms */}
          <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl p-6 border-2 border-purple-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
            <h3 className="text-2xl font-bold text-gray-800 mb-4 flex items-center">
              <span className="mr-3">🩺</span>
              Symptoms
            </h3>
            <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{diagnosis.symptoms}</p>
          </div>

          {/* Clinical Notes */}
          {diagnosis.clinical_notes && (
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border-2 border-blue-200 shadow-lg hover:shadow-xl transition-shadow duration-300">
              <h3 className="text-2xl font-bold text-gray-800 mb-4 flex items-center">
                <span className="mr-3">📋</span>
                Clinical Notes
              </h3>
              {isEditing ? (
                <textarea
                  value={editedDiagnosis.clinical_notes}
                  onChange={(e) => setEditedDiagnosis({
                    ...editedDiagnosis,
                    clinical_notes: e.target.value
                  })}
                  rows={6}
                  className="w-full px-4 py-3 border-2 border-blue-300 rounded-lg focus:ring-4 focus:ring-blue-200 focus:border-blue-500 transition-all duration-200 resize-none"
                />
              ) : (
                <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">{diagnosis.clinical_notes}</p>
              )}
            </div>
          )}

          {/* AI Analysis */}
          {diagnosis.ai_prediction && (
            <div className="bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 border-4 border-blue-300 rounded-2xl p-8 shadow-2xl">
              <div className="flex items-center mb-6 pb-5 border-b-2 border-blue-200">
                <div className="bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl p-3 shadow-lg">
                  <span className="text-4xl">🤖</span>
                </div>
                <div className="ml-4">
                  <h3 className="text-3xl font-bold text-blue-900">Med42-v3 AI Analysis</h3>
                  <p className="text-sm text-blue-700 mt-1">Clinical Decision Support</p>
                </div>
              </div>
              
              {/* Red Flag Alert */}
              {diagnosis.ai_prediction.red_flag_analysis?.has_red_flags && (
                <div className={`mb-6 p-6 rounded-xl border-4 shadow-xl ${getUrgencyColor(diagnosis.ai_prediction.red_flag_analysis.urgency_level)}`}>
                  <div className="flex items-start">
                    <span className="text-4xl mr-4">⚠️</span>
                    <div className="flex-1">
                      <h4 className={`text-2xl font-bold mb-3 ${getUrgencyTextColor(diagnosis.ai_prediction.red_flag_analysis.urgency_level)}`}>
                        RED FLAGS DETECTED - {diagnosis.ai_prediction.red_flag_analysis.urgency_level} Priority
                      </h4>
                      <div className="space-y-3">
                        {diagnosis.ai_prediction.red_flag_analysis.detected_flags.map((flag, idx) => (
                          <div key={idx} className="bg-white bg-opacity-70 rounded-lg p-4 shadow-md">
                            <p className="font-bold text-lg">{flag.flag.replace(/_/g, ' ').toUpperCase()}</p>
                            <p className="text-sm mt-1">Detected: <span className="font-semibold">{flag.keyword}</span></p>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Clinical Reasoning */}
              {diagnosis.ai_prediction.clinical_reasoning && (
                <div className="mb-6 bg-white rounded-xl p-6 border-2 border-blue-300 shadow-lg hover:shadow-xl transition-shadow duration-300">
                  <div className="flex items-center mb-4 pb-3 border-b border-blue-200">
                    <span className="text-3xl mr-3">💭</span>
                    <h4 className="text-xl font-bold text-gray-800">Clinical Reasoning</h4>
                  </div>
                  <div className="clinical-content">
                    {formatAIOutput(diagnosis.ai_prediction.clinical_reasoning)}
                  </div>
                </div>
              )}

              {/* Confidence Score */}
              <div className="mb-6 bg-white rounded-xl p-6 shadow-lg hover:shadow-xl transition-shadow duration-300">
                <div className="flex items-center justify-between mb-4">
                  <p className="text-lg font-semibold text-gray-700 flex items-center">
                    <span className="mr-2">📊</span>
                    AI Confidence Score:
                  </p>
                  <span className="text-3xl font-bold text-blue-700">
                    {formatPercentage(diagnosis.ai_prediction.confidence_score)}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-5 shadow-inner overflow-hidden">
                  <div 
                    className={`h-5 rounded-full transition-all duration-1000 bg-gradient-to-r ${getConfidenceGradient(safeNumber(diagnosis.ai_prediction.confidence_score))}`}
                    style={{ width: `${safeNumber(diagnosis.ai_prediction.confidence_score) * 100}%` }}
                  ></div>
                </div>
                {diagnosis.ai_prediction.interpretation && (
                  <p className="text-sm text-gray-600 mt-4 bg-blue-50 rounded-lg px-4 py-3 shadow-sm border-l-4 border-blue-400">
                    💡 {diagnosis.ai_prediction.interpretation}
                  </p>
                )}
              </div>

              {/* Keywords */}
              {diagnosis.ai_prediction.keywords && diagnosis.ai_prediction.keywords.length > 0 && (
                <div className="mb-6">
                  <p className="text-base font-semibold text-gray-700 mb-3 flex items-center">
                    <span className="mr-2">🔍</span>
                    Detected Clinical Features:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {diagnosis.ai_prediction.keywords.map((keyword, index) => (
                      <span
                        key={index}
                        className="px-4 py-2 rounded-full text-sm bg-gradient-to-r from-purple-100 to-pink-100 text-purple-800 font-semibold border-2 border-purple-200 shadow-md hover:scale-105 transition-transform duration-200 cursor-default"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Differential Diagnoses */}
              {diagnosis.ai_prediction.suggested_diagnoses && (
                <div className="mb-6">
                  <p className="text-base font-semibold text-gray-700 mb-3 flex items-center">
                    <span className="mr-2">💡</span>
                    Differential Diagnosis:
                  </p>
                  <div className="space-y-3">
                    {diagnosis.ai_prediction.suggested_diagnoses.map((diag, index) => (
                      <div
                        key={index}
                        className="flex items-center justify-between bg-white rounded-xl p-5 border-2 border-blue-100 shadow-md hover:shadow-lg transition-all duration-200"
                      >
                        <div className="flex items-center flex-1">
                          <span className={`w-10 h-10 rounded-full ${index === 0 ? 'bg-gradient-to-br from-green-500 to-green-600' : 'bg-gradient-to-br from-blue-500 to-blue-600'} text-white text-lg font-bold flex items-center justify-center mr-4 shadow-lg`}>
                            {index + 1}
                          </span>
                          <span className={`text-base ${index === 0 ? 'font-bold' : 'font-semibold'} text-gray-800`}>
                            {diag.term} {index === 0 && <span className="ml-2 text-green-600 text-sm">(Primary)</span>}
                          </span>
                        </div>
                        <div className="flex items-center ml-4">
                          <div className="w-32 sm:w-40 bg-gray-200 rounded-full h-4 mr-4 shadow-inner overflow-hidden">
                            <div 
                              className={`${index === 0 ? 'bg-gradient-to-r from-green-500 to-green-600' : 'bg-gradient-to-r from-blue-500 to-blue-600'} h-4 rounded-full transition-all duration-500`}
                              style={{ width: `${safeNumber(diag.score) * 100}%` }}
                            ></div>
                          </div>
                          <span className="text-base text-gray-700 font-bold w-16 text-right">
                            {formatPercentage(diag.score)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {diagnosis.ai_prediction.recommendations && diagnosis.ai_prediction.recommendations.length > 0 && (
                <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-6 border-2 border-green-300 shadow-lg">
                  <div className="flex items-center mb-4">
                    <span className="text-3xl mr-3">📋</span>
                    <h4 className="text-xl font-bold text-green-900">Recommended Workup</h4>
                  </div>
                  <ul className="space-y-3">
                    {diagnosis.ai_prediction.recommendations.map((rec, index) => (
                      <li key={index} className="flex items-start text-sm text-gray-700 bg-white rounded-lg p-4 shadow-sm hover:shadow-md transition-shadow">
                        <span className="text-green-600 mr-3 mt-0.5 text-xl">✓</span>
                        <span className="flex-1">{rec}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Final Diagnosis */}
          <div className="bg-gradient-to-r from-yellow-50 to-orange-50 border-4 border-yellow-300 rounded-xl p-6 shadow-lg hover:shadow-xl transition-shadow duration-300">
            <h3 className="text-2xl font-bold text-gray-800 mb-4 flex items-center">
              <span className="mr-3">🔬</span>
              Final Diagnosis
            </h3>
            {isEditing ? (
              <textarea
                value={editedDiagnosis.diagnosis_text}
                onChange={(e) => setEditedDiagnosis({
                  ...editedDiagnosis,
                  diagnosis_text: e.target.value
                })}
                rows={6}
                className="w-full px-4 py-3 border-2 border-yellow-300 rounded-lg focus:ring-4 focus:ring-yellow-200 focus:border-yellow-500 transition-all duration-200 resize-none"
              />
            ) : (
              <p className="text-gray-800 font-semibold whitespace-pre-wrap leading-relaxed text-lg">{diagnosis.diagnosis_text}</p>
            )}
          </div>

          {/* Medications */}
          {diagnosis.medications && diagnosis.medications.length > 0 && (
            <div>
              <h3 className="text-2xl font-bold text-gray-800 mb-4 flex items-center">
                <span className="mr-3">💊</span>
                Prescribed Medications
              </h3>
              <div className="space-y-4">
                {diagnosis.medications.map((med) => (
                  <div
                    key={med.id}
                    className="bg-gradient-to-r from-purple-50 to-pink-50 border-2 border-purple-300 rounded-xl p-6 shadow-md hover:shadow-lg transition-shadow duration-300"
                  >
                    <h4 className="font-bold text-purple-900 text-xl mb-4">{med.medication_name}</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
                      <div className="bg-white rounded-lg p-4 shadow-sm">
                        <span className="text-gray-600 font-semibold text-sm block mb-1">💊 Dosage:</span>
                        <p className="font-bold text-gray-800">{med.dosage}</p>
                      </div>
                      <div className="bg-white rounded-lg p-4 shadow-sm">
                        <span className="text-gray-600 font-semibold text-sm block mb-1">⏰ Frequency:</span>
                        <p className="font-bold text-gray-800">{med.frequency}</p>
                      </div>
                      <div className="bg-white rounded-lg p-4 shadow-sm">
                        <span className="text-gray-600 font-semibold text-sm block mb-1">📅 Duration:</span>
                        <p className="font-bold text-gray-800">{med.duration}</p>
                      </div>
                    </div>
                    {med.instructions && (
                      <div className="pt-4 border-t-2 border-purple-200">
                        <span className="text-gray-700 font-semibold text-sm block mb-2">📝 Instructions:</span>
                        <p className="text-gray-700 bg-white rounded-lg p-3 shadow-sm">{med.instructions}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Approval Info */}
          {diagnosis.approved_at && (
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 border-4 border-green-300 rounded-xl p-6 shadow-lg">
              <p className="text-base text-green-800 font-bold flex items-center">
                <span className="text-3xl mr-3">✓</span>
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