'use client';

import { useState, useEffect } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { profileApi } from '@/lib/api';
import { Search, Plus, MapPin, Briefcase, Edit, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';

interface JobSearchProfile {
  id: string;
  keywords: string;
  location: string;
  created_at: string;
}

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<JobSearchProfile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [keywords, setKeywords] = useState('');
  const [location, setLocation] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadProfiles = async () => {
    setIsLoading(true);
    try {
      const data = await profileApi.list();
      setProfiles(data);
    } catch (error) {
      console.error('Failed to load profiles:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadProfiles();
  }, []);

  const handleCreateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await profileApi.create({ keywords, location });
      toast.success('Profile created successfully!');
      setShowModal(false);
      setKeywords('');
      setLocation('');
      loadProfiles();
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to create profile';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <DashboardLayout>
      <div className="page-container">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Job Search Profiles</h1>
            <p className="text-gray-600">Define your job search preferences</p>
          </div>
          <button
            onClick={() => setShowModal(true)}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="h-5 w-5" />
            New Profile
          </button>
        </div>

        {/* Profiles Grid */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-linkedin-blue"></div>
          </div>
        ) : profiles.length === 0 ? (
          <div className="card text-center py-12">
            <Search className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-2">No search profiles yet</p>
            <p className="text-sm text-gray-400 mb-4">Create a profile to start finding jobs</p>
            <button
              onClick={() => setShowModal(true)}
              className="btn-primary"
            >
              Create Your First Profile
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {profiles.map((profile) => (
              <div key={profile.id} className="card">
                <div className="flex justify-between items-start mb-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Search className="h-5 w-5 text-linkedin-blue" />
                  </div>
                  <div className="flex gap-1">
                    <button className="p-2 text-gray-400 hover:text-linkedin-blue hover:bg-gray-100 rounded-lg transition-colors">
                      <Edit className="h-4 w-4" />
                    </button>
                    <button className="p-2 text-gray-400 hover:text-red-500 hover:bg-gray-100 rounded-lg transition-colors">
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
                <h3 className="font-semibold text-gray-900 mb-2">{profile.keywords}</h3>
                <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
                  <MapPin className="h-4 w-4" />
                  {profile.location}
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-400">Created {formatDate(profile.created_at)}</span>
                  <a
                    href={`/dashboard/jobs?profile=${profile.id}`}
                    className="text-linkedin-blue hover:text-linkedin-dark font-medium"
                  >
                    View Jobs →
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Create Profile Modal */}
        {showModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div
              className="absolute inset-0 bg-black bg-opacity-50"
              onClick={() => setShowModal(false)}
            />
            <div className="relative bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">Create Search Profile</h2>
              <form onSubmit={handleCreateProfile}>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Job Keywords
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <Briefcase className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="text"
                        value={keywords}
                        onChange={(e) => setKeywords(e.target.value)}
                        className="input-field pl-10"
                        placeholder="e.g., Software Engineer, React Developer"
                        required
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Location
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <MapPin className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="text"
                        value={location}
                        onChange={(e) => setLocation(e.target.value)}
                        className="input-field pl-10"
                        placeholder="e.g., San Francisco, Remote"
                        required
                      />
                    </div>
                  </div>
                </div>
                <div className="flex gap-3 mt-6">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="btn-secondary flex-1"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="btn-primary flex-1"
                  >
                    {isSubmitting ? 'Creating...' : 'Create Profile'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
