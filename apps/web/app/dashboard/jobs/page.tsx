'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import DashboardLayout from '@/components/DashboardLayout';
import { jobsApi, profileApi } from '@/lib/api';
import { Briefcase, MapPin, ExternalLink, RefreshCw, CheckCircle, Clock, XCircle, Zap } from 'lucide-react';
import toast from 'react-hot-toast';
import clsx from 'clsx';

interface Job {
  id: string;
  linkedin_job_id: string;
  title: string;
  company: string;
  location: string;
  job_url: string;
  easy_apply: boolean;
  status: string;
  discovered_at: string;
}

interface JobSearchProfile {
  id: string;
  keywords: string;
  location: string;
}

function JobsContent() {
  const searchParams = useSearchParams();
  const profileIdFromUrl = searchParams.get('profile');

  const [profiles, setProfiles] = useState<JobSearchProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>(profileIdFromUrl || '');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<string | null>(null);

  useEffect(() => {
    loadProfiles();
  }, []);

  useEffect(() => {
    if (selectedProfileId) {
      loadJobs();
    }
  }, [selectedProfileId, statusFilter]);

  useEffect(() => {
    if (profileIdFromUrl) {
      setSelectedProfileId(profileIdFromUrl);
    }
  }, [profileIdFromUrl]);

  useEffect(() => {
    if (taskId && taskStatus === 'running') {
      const interval = setInterval(async () => {
        try {
          const status = await jobsApi.getSearchStatus(taskId);
          setTaskStatus(status.status);
          if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(interval);
            if (status.status === 'completed') {
              toast.success(`Found ${status.jobs_found} jobs!`);
              loadJobs();
            } else {
              toast.error('Job search failed');
            }
          }
        } catch (error) {
          clearInterval(interval);
        }
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [taskId, taskStatus]);

  const loadProfiles = async () => {
    try {
      const data = await profileApi.list();
      setProfiles(data);
      if (data.length > 0 && !selectedProfileId) {
        setSelectedProfileId(data[0].id);
      }
    } catch (error) {
      console.error('Failed to load profiles:', error);
    }
  };

  const loadJobs = async () => {
    if (!selectedProfileId) return;
    setIsLoading(true);
    try {
      const data = await jobsApi.list(selectedProfileId, statusFilter || undefined);
      setJobs(data.jobs || []);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!selectedProfileId) {
      toast.error('Please select a profile first');
      return;
    }

    setIsSearching(true);
    try {
      const result = await jobsApi.triggerSearch(selectedProfileId);
      setTaskId(result.task_id);
      setTaskStatus(result.status);
      toast.success('Job search started!');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to start job search';
      toast.error(message);
    } finally {
      setIsSearching(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'discovered':
        return <Clock className="h-4 w-4 text-gray-400" />;
      case 'viewed':
        return <CheckCircle className="h-4 w-4 text-blue-500" />;
      case 'applied':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      discovered: 'bg-gray-100 text-gray-600',
      viewed: 'bg-blue-100 text-blue-600',
      applied: 'bg-green-100 text-green-600',
      failed: 'bg-red-100 text-red-600',
    };
    return styles[status] || styles.discovered;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <DashboardLayout>
      <div className="page-container">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Jobs</h1>
            <p className="text-gray-600">Discover and track job opportunities</p>
          </div>
          <button
            onClick={handleSearch}
            disabled={isSearching || taskStatus === 'running'}
            className="btn-primary flex items-center gap-2"
          >
            {isSearching || taskStatus === 'running' ? (
              <>
                <RefreshCw className="h-5 w-5 animate-spin" />
                Searching...
              </>
            ) : (
              <>
                <RefreshCw className="h-5 w-5" />
                Search Jobs
              </>
            )}
          </button>
        </div>

        {/* Filters */}
        <div className="card mb-6">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search Profile
              </label>
              <select
                value={selectedProfileId}
                onChange={(e) => setSelectedProfileId(e.target.value)}
                className="input-field"
              >
                <option value="">Select a profile...</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.keywords} - {profile.location}
                  </option>
                ))}
              </select>
            </div>
            <div className="sm:w-48">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Status
              </label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="input-field"
              >
                <option value="">All Status</option>
                <option value="discovered">Discovered</option>
                <option value="viewed">Viewed</option>
                <option value="applied">Applied</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          </div>
        </div>

        {/* Jobs List */}
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-linkedin-blue"></div>
          </div>
        ) : !selectedProfileId ? (
          <div className="card text-center py-12">
            <Briefcase className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-2">Select a search profile to view jobs</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="card text-center py-12">
            <Briefcase className="h-12 w-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500 mb-2">No jobs found</p>
            <p className="text-sm text-gray-400 mb-4">Start a search to discover jobs</p>
            <button onClick={handleSearch} className="btn-primary">
              Search Jobs
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {jobs.map((job) => (
              <div key={job.id} className="card hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Briefcase className="h-5 w-5 text-linkedin-blue" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-gray-900">{job.title}</h3>
                        <p className="text-gray-600">{job.company}</p>
                        <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                          <div className="flex items-center gap-1">
                            <MapPin className="h-4 w-4" />
                            {job.location}
                          </div>
                          <div className="flex items-center gap-1">
                            {getStatusIcon(job.status)}
                            <span className={clsx('px-2 py-0.5 rounded-full text-xs font-medium', getStatusBadge(job.status))}>
                              {job.status}
                            </span>
                          </div>
                          {job.easy_apply && (
                            <div className="flex items-center gap-1 text-green-600">
                              <Zap className="h-4 w-4" />
                              Easy Apply
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-400">{formatDate(job.discovered_at)}</span>
                    <a
                      href={job.job_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 text-gray-500 hover:text-linkedin-blue hover:bg-gray-100 rounded-lg transition-colors"
                    >
                      <ExternalLink className="h-5 w-5" />
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={
      <DashboardLayout>
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-linkedin-blue"></div>
        </div>
      </DashboardLayout>
    }>
      <JobsContent />
    </Suspense>
  );
}
