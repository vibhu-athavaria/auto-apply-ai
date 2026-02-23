import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 || error.response?.status === 403) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  register: async (email: string, password: string) => {
    const response = await api.post('/auth/register', { email, password });
    return response.data;
  },

  login: async (email: string, password: string) => {
    const response = await api.post('/auth/login', { email, password });
    return response.data;
  },
};

// Resume API
export const resumeApi = {
  upload: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/resumes/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  list: async () => {
    const response = await api.get('/resumes/');
    return response.data;
  },
};

// Job Search Profile API
export const profileApi = {
  create: async (data: { keywords: string; location: string }) => {
    const response = await api.post('/profiles/', data);
    return response.data;
  },

  list: async () => {
    const response = await api.get('/profiles/');
    return response.data;
  },

  get: async (id: string) => {
    const response = await api.get(`/profiles/${id}`);
    return response.data;
  },
};

// Jobs API
export const jobsApi = {
  list: async (searchProfileId: string, status?: string) => {
    const params = new URLSearchParams({ search_profile_id: searchProfileId });
    if (status) params.append('status', status);
    const response = await api.get(`/jobs/?${params.toString()}`);
    return response.data;
  },

  triggerSearch: async (searchProfileId: string) => {
    const response = await api.post('/jobs/search', {
      search_profile_id: searchProfileId,
    });
    return response.data;
  },

  getSearchStatus: async (taskId: string) => {
    const response = await api.get(`/jobs/search/status/${taskId}`);
    return response.data;
  },

  apply: async (jobId: string, tailoredResumeId?: string) => {
    const params = tailoredResumeId ? `?tailored_resume_id=${tailoredResumeId}` : '';
    const response = await api.post(`/jobs/${jobId}/apply${params}`);
    return response.data;
  },

  tailor: async (jobId: string, resumeId: string) => {
    const response = await api.post(`/jobs/${jobId}/tailor`, { resume_id: resumeId });
    return response.data;
  },
};

// Applications API
export const applicationsApi = {
  list: async (status?: string) => {
    const params = status ? `?status=${status}` : '';
    const response = await api.get(`/jobs/applications${params}`);
    return response.data;
  },

  get: async (applicationId: string) => {
    const response = await api.get(`/jobs/applications/${applicationId}`);
    return response.data;
  },

  getTaskStatus: async (taskId: string) => {
    const response = await api.get(`/jobs/applications/task/${taskId}`);
    return response.data;
  },
};

// LinkedIn API
export const linkedinApi = {
  getStatus: async () => {
    const response = await api.get('/linkedin/session');
    return response.data;
  },

  connect: async (email: string, password: string) => {
    const response = await api.post('/linkedin/connect', { email, password });
    return response.data;
  },

  getConnectStatus: async (taskId: string) => {
    const response = await api.get(`/linkedin/connect/status/${taskId}`);
    return response.data;
  },

  validate: async () => {
    const response = await api.post('/linkedin/session/validate');
    return response.data;
  },

  deleteSession: async () => {
    const response = await api.delete('/linkedin/session');
    return response.data;
  },
};

export default api;
