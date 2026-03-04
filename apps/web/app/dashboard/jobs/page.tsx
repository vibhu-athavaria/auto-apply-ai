'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import DashboardLayout from '@/components/DashboardLayout';
import { jobsApi, profileApi, resumeApi, linkedinApi } from '@/lib/api';
import { Briefcase, MapPin, ExternalLink, RefreshCw, CheckCircle, Clock, XCircle, Zap, Send, FileText, Loader2, Search } from 'lucide-react';
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

interface LinkedInStatus {
  connected: boolean;
  status: string;
}

interface Resume {
  id: string;
  filename: string;
}

interface TailoredResume {
  id: string;
  job_id: string;
  tailored_resume_text: string;
  cover_letter_text?: string;
}

function JobsContent() {
  const searchParams = useSearchParams();
  const profileIdFromUrl = searchParams.get('profile');

  const [profiles, setProfiles] = useState<JobSearchProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>(profileIdFromUrl || '');
  const [selectedProfile, setSelectedProfile] = useState<JobSearchProfile | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<string | null>(null);

  const [resumes, setResumes] = useState<Resume[]>([]);
  const [tailoredResumes, setTailoredResumes] = useState<Record<string, TailoredResume>>({});
  const [applyingJobs, setApplyingJobs] = useState<Set<string>>(new Set());
  const [tailoringJobs, setTailoringJobs] = useState<Set<string>>(new Set());
  const [selectedResumeId, setSelectedResumeId] = useState<string>('');
  const [showApplyModal, setShowApplyModal] = useState<string | null>(null);
  const [applicationTasks, setApplicationTasks] = useState<Record<string, string>>({});
  const [linkedinStatus, setLinkedinStatus] = useState<LinkedInStatus>({ connected: false, status: 'not_set' });
  const [searchMessage, setSearchMessage] = useState<string>('');
  const [jobsFound, setJobsFound] = useState<number>(0);

  useEffect(() => {
    loadProfiles();
    loadResumes();
    checkLinkedInStatus();
  }, []);

  useEffect(() => {
    if (selectedProfileId) {
      const profile = profiles.find(p => p.id === selectedProfileId);
      setSelectedProfile(profile || null);
      loadJobs();
    }
  }, [selectedProfileId, statusFilter, profiles]);

  useEffect(() => {
    if (profileIdFromUrl) {
      setSelectedProfileId(profileIdFromUrl);
    }
  }, [profileIdFromUrl]);

  useEffect(() => {
    if (taskId && (taskStatus === 'running' || taskStatus === 'queued')) {
      const interval = setInterval(async () => {
        try {
          const status = await jobsApi.getSearchStatus(taskId);
          setTaskStatus(status.status);

          if (status.message) {
            setSearchMessage(status.message);
          }

          if (status.jobs_found !== undefined) {
            setJobsFound(status.jobs_found);
          }

          if (status.status === 'running') {
            loadJobs();
          }

          if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(interval);
            setIsSearching(false);
            if (status.status === 'completed') {
              toast.success(`Found ${status.jobs_found} jobs!`);
              loadJobs();
            } else {
              toast.error(status.message || 'Job search failed');
            }
            setSearchMessage('');
            setTaskId(null);
            setTaskStatus(null);
          }
        } catch (error) {
          clearInterval(interval);
          setIsSearching(false);
          setSearchMessage('');
        }
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [taskId, taskStatus]);

  useEffect(() => {
    const taskIds = Object.values(applicationTasks);
    if (taskIds.length > 0) {
      const interval = setInterval(async () => {
        for (const [jobId, taskId] of Object.entries(applicationTasks)) {
          try {
            const status = await jobsApi.getSearchStatus(taskId);
            if (status.status === 'completed' || status.status === 'failed') {
              setApplicationTasks(prev => {
                const updated = { ...prev };
                delete updated[jobId];
                return updated;
              });
              if (status.status === 'completed') {
                toast.success('Application submitted!');
                loadJobs();
              } else {
                toast.error('Application failed');
              }
            }
          } catch (error) {
          }
        }
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [applicationTasks]);

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

  const loadResumes = async () => {
    try {
      const data = await resumeApi.list();
      setResumes(data);
      if (data.length > 0) {
        setSelectedResumeId(data[0].id);
      }
    } catch (error) {
      console.error('Failed to load resumes:', error);
    }
  };

  const checkLinkedInStatus = async () => {
    try {
      const data = await linkedinApi.getStatus();
      setLinkedinStatus({
        connected: data.connected === true || data.status === 'connected',
        status: data.status,
      });
    } catch (error) {
      console.error('Failed to check LinkedIn status:', error);
      setLinkedinStatus({ connected: false, status: 'not_set' });
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

    if (!linkedinStatus?.connected) {
      toast.error('Please connect your LinkedIn account first');
      return;
    }

    setIsSearching(true);
    setJobsFound(0);
    setSearchMessage('Initializing job search...');
    try {
      const result = await jobsApi.triggerSearch(selectedProfileId);
      setTaskId(result.task_id);
      setTaskStatus(result.status);
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to start job search';
      toast.error(message);
      setIsSearching(false);
      setSearchMessage('');
    }
  };

  const handleTailor = async (jobId: string) => {
    if (!selectedResumeId) {
      toast.error('Please upload a resume first');
      return;
    }

    setTailoringJobs(prev => new Set(prev).add(jobId));
    try {
      const result = await jobsApi.tailor(jobId, selectedResumeId);
      setTailoredResumes(prev => ({
        ...prev,
        [jobId]: result
      }));
      toast.success('Resume tailored successfully!');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to tailor resume';
      toast.error(message);
    } finally {
      setTailoringJobs(prev => {
        const updated = new Set(prev);
        updated.delete(jobId);
        return updated;
      });
    }
  };

  const handleApply = async (jobId: string) => {
    const tailoredResume = tailoredResumes[jobId];

    setApplyingJobs(prev => new Set(prev).add(jobId));
    setShowApplyModal(null);

    try {
      const result = await jobsApi.apply(jobId, tailoredResume?.id);
      setApplicationTasks(prev => ({
        ...prev,
        [jobId]: result.task_id
      }));
      toast.success('Application queued!');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to apply';
      toast.error(message);
    } finally {
      setApplyingJobs(prev => {
        const updated = new Set(prev);
        updated.delete(jobId);
        return updated;
      });
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

  const isSearchInProgress = isSearching || taskStatus === 'running' || taskStatus === 'queued';

  return (
    <DashboardLayout>
      <div className="page-container">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Jobs</h1>
            <p className="text-gray-600">Discover and track job opportunities</p>
          </div>
          <div className="flex items-center gap-3">
            {linkedinStatus.connected ? (
              <span className="text-sm text-green-600 flex items-center gap-1">
                <CheckCircle className="h-4 w-4" />
                LinkedIn Connected
              </span>
            ) : (
              <a href="/dashboard/linkedin" className="text-sm text-blue-600 hover:underline">
                Connect LinkedIn first
              </a>
            )}
            <button
              onClick={handleSearch}
              disabled={isSearchInProgress || !linkedinStatus?.connected}
              className="btn-primary flex items-center gap-2"
            >
              {isSearchInProgress ? (
                <>
                  <RefreshCw className="h-5 w-5 animate-spin" />
                  Searching...
                </>
              ) : (
                <>
                  <Search className="h-5 w-5" />
                  Search Jobs
                </>
              )}
            </button>
          </div>
        </div>

        {isSearchInProgress && (
          <div className="card mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                  <RefreshCw className="h-6 w-6 text-blue-600 animate-spin" />
                </div>
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-blue-900 mb-2">
                  Searching LinkedIn for Jobs
                </h3>
                <div className="space-y-2">
                  <p className="text-blue-700 font-medium">{searchMessage}</p>
                  {jobsFound > 0 && (
                    <p className="text-sm text-blue-600">
                      Found <span className="font-bold text-blue-800">{jobsFound}</span> jobs so far...
                    </p>
                  )}
                  <p className="text-xs text-blue-500 mt-2">
                    This may take 30-60 seconds while we search and process results
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

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
                disabled={isSearchInProgress}
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
            <p className="text-sm text-gray-400 mb-4">
              {isSearchInProgress
                ? 'Jobs will appear here as they are discovered...'
                : 'Click "Search Jobs" to discover opportunities'}
            </p>
            {!isSearchInProgress && (
              <button
                onClick={handleSearch}
                disabled={!linkedinStatus?.connected}
                className="btn-primary disabled:opacity-50"
              >
                Search Jobs
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm text-gray-600">
                {jobs.length} job{jobs.length !== 1 ? 's' : ''} found
                {isSearchInProgress && ' (searching...)'}
              </span>
            </div>
            <div className="space-y-4">
              {jobs.map((job) => {
                const isApplying = applyingJobs.has(job.id);
                const isTailoring = tailoringJobs.has(job.id);
                const hasTailored = !!tailoredResumes[job.id];
                const isApplied = job.status === 'applied';
                const isQueued = !!applicationTasks[job.id];

                return (
                  <div key={job.id} className="card hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                            <Briefcase className="h-5 w-5 text-linkedin-blue" />
                          </div>
                          <div className="flex-1">
                            <h3 className="font-semibold text-gray-900">{job.title}</h3>
                            <p className="text-gray-600">{job.company}</p>
                            <div className="flex items-center gap-4 mt-2 text-sm text-gray-500 flex-wrap">
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
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className="text-sm text-gray-400 mr-2">{formatDate(job.discovered_at)}</span>
                        <a
                          href={job.job_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-2 text-gray-500 hover:text-linkedin-blue hover:bg-gray-100 rounded-lg transition-colors"
                          title="View on LinkedIn"
                        >
                          <ExternalLink className="h-5 w-5" />
                        </a>
                      </div>
                    </div>

                    {job.easy_apply && !isApplied && (
                      <div className="mt-4 pt-4 border-t border-gray-100 flex items-center gap-3 flex-wrap">
                        <button
                          onClick={() => handleTailor(job.id)}
                          disabled={isTailoring || !selectedResumeId}
                          className={clsx(
                            "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                            hasTailored
                              ? "bg-green-100 text-green-700 hover:bg-green-200"
                              : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                          )}
                        >
                          {isTailoring ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Tailoring...
                            </>
                          ) : hasTailored ? (
                            <>
                              <CheckCircle className="h-4 w-4" />
                              Tailored
                            </>
                          ) : (
                            <>
                              <FileText className="h-4 w-4" />
                              Tailor Resume
                            </>
                          )}
                        </button>

                        <button
                          onClick={() => setShowApplyModal(job.id)}
                          disabled={isApplying || isQueued}
                          className={clsx(
                            "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                            isQueued
                              ? "bg-yellow-100 text-yellow-700"
                              : "btn-primary py-1.5"
                          )}
                        >
                          {isApplying ? (
                            <>
                              <Loader2 className="h-4 w-4 animate-spin" />
                              Applying...
                            </>
                          ) : isQueued ? (
                            <>
                              <Clock className="h-4 w-4" />
                              Queued
                            </>
                          ) : (
                            <>
                              <Send className="h-4 w-4" />
                              Apply
                            </>
                          )}
                        </button>
                      </div>
                    )}

                    {isApplied && (
                      <div className="mt-4 pt-4 border-t border-gray-100">
                        <span className="text-sm text-green-600 flex items-center gap-1">
                          <CheckCircle className="h-4 w-4" />
                          Application submitted
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}

        {showApplyModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
              <h3 className="text-lg font-semibold mb-4">Confirm Application</h3>
              <p className="text-gray-600 mb-4">
                Are you sure you want to apply to this job? This will use your {tailoredResumes[showApplyModal] ? 'tailored resume' : 'default resume'}.
              </p>
              <div className="flex gap-3 justify-end">
                <button
                  onClick={() => setShowApplyModal(null)}
                  className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleApply(showApplyModal)}
                  className="btn-primary"
                >
                  Apply Now
                </button>
              </div>
            </div>
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
