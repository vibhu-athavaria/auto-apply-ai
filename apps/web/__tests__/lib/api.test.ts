import axios from 'axios';
import { authApi, resumeApi, profileApi, jobsApi } from '@/lib/api';

// Get the mocked axios instance
const mockedAxios = axios.create() as jest.Mocked<typeof axios>;

describe('API Client', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Mock localStorage
    Storage.prototype.getItem = jest.fn(() => 'test-token');
  });

  describe('authApi', () => {
    it('login should call correct endpoint', async () => {
      const mockResponse = { access_token: 'token', token_type: 'bearer' };
      mockedAxios.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await authApi.login('test@example.com', 'password');

      expect(mockedAxios.post).toHaveBeenCalledWith(
        '/auth/login',
        { email: 'test@example.com', password: 'password' }
      );
      expect(result).toEqual(mockResponse);
    });

    it('register should call correct endpoint', async () => {
      const mockResponse = { id: '1', email: 'test@example.com' };
      mockedAxios.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await authApi.register('test@example.com', 'password');

      expect(mockedAxios.post).toHaveBeenCalledWith(
        '/auth/register',
        { email: 'test@example.com', password: 'password' }
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe('resumeApi', () => {
    it('upload should send FormData with correct headers', async () => {
      const mockFile = new File(['test'], 'resume.pdf', { type: 'application/pdf' });
      const mockResponse = { id: '1', filename: 'resume.pdf' };
      mockedAxios.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await resumeApi.upload(mockFile);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        '/resumes/upload',
        expect.any(FormData),
        expect.objectContaining({
          headers: { 'Content-Type': 'multipart/form-data' },
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('list should call correct endpoint', async () => {
      const mockResponse = [{ id: '1', filename: 'resume.pdf' }];
      mockedAxios.get.mockResolvedValueOnce({ data: mockResponse });

      const result = await resumeApi.list();

      expect(mockedAxios.get).toHaveBeenCalledWith('/resumes/');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('profileApi', () => {
    it('create should call correct endpoint', async () => {
      const profileData = { keywords: 'Software Engineer', location: 'Remote' };
      const mockResponse = { id: '1', ...profileData };
      mockedAxios.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await profileApi.create(profileData);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        '/profiles/',
        profileData
      );
      expect(result).toEqual(mockResponse);
    });

    it('list should call correct endpoint', async () => {
      const mockResponse = [{ id: '1', keywords: 'Engineer' }];
      mockedAxios.get.mockResolvedValueOnce({ data: mockResponse });

      const result = await profileApi.list();

      expect(mockedAxios.get).toHaveBeenCalledWith('/profiles/');
      expect(result).toEqual(mockResponse);
    });

    it('get should call correct endpoint', async () => {
      const mockResponse = { id: '1', keywords: 'Engineer' };
      mockedAxios.get.mockResolvedValueOnce({ data: mockResponse });

      const result = await profileApi.get('profile-id');

      expect(mockedAxios.get).toHaveBeenCalledWith('/profiles/profile-id');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('jobsApi', () => {
    it('list should call correct endpoint with profile_id', async () => {
      const mockResponse = { jobs: [], total: 0 };
      mockedAxios.get.mockResolvedValueOnce({ data: mockResponse });

      const result = await jobsApi.list('profile-id');

      expect(mockedAxios.get).toHaveBeenCalledWith('/jobs/?search_profile_id=profile-id');
      expect(result).toEqual(mockResponse);
    });

    it('triggerSearch should call correct endpoint', async () => {
      const mockResponse = { task_id: 'task-1', status: 'running' };
      mockedAxios.post.mockResolvedValueOnce({ data: mockResponse });

      const result = await jobsApi.triggerSearch('profile-id');

      expect(mockedAxios.post).toHaveBeenCalledWith('/jobs/search', {
        search_profile_id: 'profile-id',
      });
      expect(result).toEqual(mockResponse);
    });

    it('getSearchStatus should call correct endpoint', async () => {
      const mockResponse = { status: 'completed', jobs_found: 10 };
      mockedAxios.get.mockResolvedValueOnce({ data: mockResponse });

      const result = await jobsApi.getSearchStatus('task-id');

      expect(mockedAxios.get).toHaveBeenCalledWith('/jobs/search/status/task-id');
      expect(result).toEqual(mockResponse);
    });
  });
});