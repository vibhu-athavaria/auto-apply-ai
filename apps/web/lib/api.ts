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
};

export default api;
