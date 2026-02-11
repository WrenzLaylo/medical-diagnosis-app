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

  analyzeSymptomsStream: async (
    data: { symptoms: string; clinical_notes?: string },
    handlers: {
      onStatus?: (payload: any) => void;
      onToken?: (payload: any) => void;
      onValidation?: (payload: any) => void;
      onError?: (payload: any) => void;
      onDone?: (payload: any) => void;
    } = {}
  ) => {
    const response = await fetch(`${API_BASE_URL}/diagnoses/analyze_stream/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Stream request failed (${response.status}): ${errorText}`);
    }

    if (!response.body) {
      throw new Error('Stream response body is not available');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let donePayload: any = null;

    const processEvent = (eventBlock: string) => {
      const lines = eventBlock.split(/\r?\n/);
      let eventName = 'message';
      const dataLines: string[] = [];

      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim();
          continue;
        }
        if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim());
        }
      }

      if (dataLines.length === 0) {
        return;
      }

      let payload: any = dataLines.join('\n');
      try {
        payload = JSON.parse(payload);
      } catch (_parseError) {
        // Keep raw string payload
      }

      if (eventName === 'status' && handlers.onStatus) handlers.onStatus(payload);
      if (eventName === 'token' && handlers.onToken) handlers.onToken(payload);
      if (eventName === 'validation' && handlers.onValidation) handlers.onValidation(payload);
      if (eventName === 'error' && handlers.onError) handlers.onError(payload);
      if (eventName === 'done') {
        donePayload = payload;
        if (handlers.onDone) handlers.onDone(payload);
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop() || '';

      for (const eventBlock of events) {
        if (eventBlock.trim()) {
          processEvent(eventBlock);
        }
      }
    }

    const flushed = decoder.decode();
    if (flushed) {
      buffer += flushed;
    }
    if (buffer.trim()) {
      processEvent(buffer.trim());
    }

    return donePayload;
  },
  
  addMedication: (diagnosisId: number, data: any) => {
    console.log('Adding medication:', data);
    return api.post(`/diagnoses/${diagnosisId}/add_medication/`, data);
  },
};

export default api;
