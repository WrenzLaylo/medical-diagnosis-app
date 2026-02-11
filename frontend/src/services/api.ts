import axios from 'axios';

const resolveApiBaseUrl = (): string => {
  if (process.env.REACT_APP_API_BASE_URL) {
    return process.env.REACT_APP_API_BASE_URL;
  }

  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000/api`;
  }

  return 'http://localhost:8000/api';
};

const API_BASE_URL = resolveApiBaseUrl();

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds timeout
});

// Add response interceptor for better error handling
api.interceptors.response.use(
  (response) => {
    // Handle paginated responses from DRF
    // If response has 'results' key, extract it
    if (response.data && typeof response.data === 'object' && 'results' in response.data) {
      console.log('Detected paginated response, extracting results array');
      response.data = response.data.results;
    }
    return response;
  },
  (error) => {
    console.error('API Error:', error);
    if (error.response) {
      console.error('Error Response:', error.response.data);
    }
    return Promise.reject(error);
  }
);

export const diagnosisAPI = {
  getAllDiagnoses: () => api.get('/diagnoses/'),
  
  getDiagnosis: (id: number) => api.get(`/diagnoses/${id}/`),
  
  createDiagnosis: (data: any) => {
    console.log('Creating diagnosis with data:', data);
    return api.post('/diagnoses/', data);
  },
  
  updateDiagnosis: (id: number, data: any) => 
    api.patch(`/diagnoses/${id}/update_diagnosis/`, data),
  
  approveDiagnosis: (id: number) => 
    api.post(`/diagnoses/${id}/approve/`),
  
  analyzeSymptoms: (data: { symptoms: string; clinical_notes?: string }) => 
    api.post('/diagnoses/analyze_symptoms/', data),
  
  addMedication: (diagnosisId: number, data: any) => {
    console.log('Adding medication:', data);
    return api.post(`/diagnoses/${diagnosisId}/add_medication/`, data);
  },
};

export default api;
