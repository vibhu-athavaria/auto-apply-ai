'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import DashboardLayout from '@/components/DashboardLayout';
import { jobsApi, profileApi, resumeApi, linkedinApi } from '@/lib/api';
import {
  Briefcase, MapPin, ExternalLink, RefreshCw, CheckCircle, Clock, XCircle,
  Zap, Send, FileText, Loader2, Search, ChevronLeft, ChevronRight,
  FileEdit, FileSpreadsheet, Eye, Award, X
} from 'lucide-react';
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
  description?: string;
  match_score?: number;
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
  cover_letter?: string;
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

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalJobs, setTotalJobs] = useState(0);
  const jobsPerPage = 10;

  const [resumes, setResumes] = useState<Resume[]>([]);
  const [tailoredResumes, setTailoredResumes] = useState<Record<string, TailoredResume>>({});
  const [matchScores, setMatchScores] = useState<Record<string, number>>({});
  const [calculatingScores, setCalculatingScores] = useState<Set<string>>(new Set());
  const [applyingJobs, setApplyingJobs] = useState<Set<string>>(new Set());
  const [tailoringJobs, setTailoringJobs] = useState<Set<string>>(new Set());
  const [tailoringCoverLetterJobs, setTailoringCoverLetterJobs] = useState<Set<string>>(new Set());
  const [selectedResumeId, setSelectedResumeId] = useState<string>('');
  const [showApplyModal, setShowApplyModal] = useState<string | null>(null);
  const [showDetailsModal, setShowDetailsModal] = useState<Job | null>(null);
  const [showTailoredModal, setShowTailoredModal] = useState<{jobId: string, type: 'resume' | 'cover_letter'} | null>(null);
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
      setCurrentPage(1); // Reset to first page when profile changes
      loadJobs();
    }
  }, [selectedProfileId, statusFilter, profiles]);

  useEffect(() => {
    if (profileIdFromUrl) {
      setSelectedProfileId(profileIdFromUrl);
    }
  }, [profileIdFromUrl]);

  useEffect(() => {
    loadJobs();
  }, [currentPage]);

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
      const offset = (currentPage - 1) * jobsPerPage;
      const data = await jobsApi.list(selectedProfileId, statusFilter || undefined, jobsPerPage, offset);
      setJobs(data.jobs || []);
      setTotalJobs(data.total || 0);

      // Fetch match scores for jobs
      fetchMatchScores(data.jobs || []);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchMatchScores = async (jobsList: Job[]) => {
    for (const job of jobsList) {
      if (!job.match_score && !calculatingScores.has(job.id)) {
        setCalculatingScores(prev => new Set(prev).add(job.id));
        try {
          const result = await jobsApi.getMatchScore(job.id, selectedResumeId);
          setMatchScores(prev => ({ ...prev, [job.id]: result.score }));
        } catch (error) {
          console.error(`Failed to fetch match score for job ${job.id}:`, error);
        } finally {
          setCalculatingScores(prev => {
            const updated = new Set(prev);
            updated.delete(job.id);
            return updated;
          });
        }
      }
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
        [jobId]: result.tailored_resume
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

  const handleTailorCoverLetter = async (jobId: string) => {
    if (!selectedResumeId) {
      toast.error('Please upload a resume first');
      return;
    }

    setTailoringCoverLetterJobs(prev => new Set(prev).add(jobId));
    try {
      const result = await jobsApi.tailor(jobId, selectedResumeId);
      setTailoredResumes(prev => ({
        ...prev,
        [jobId]: result.tailored_resume
      }));
      toast.success('Cover letter generated successfully!');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to generate cover letter';
      toast.error(message);
    } finally {
      setTailoringCoverLetterJobs(prev => {
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

  const getMatchScoreColor = (score: number) => {
    if (score >= 80) return 'bg-green-500 text-white';
    if (score >= 60) return 'bg-yellow-500 text-white';
    if (score >= 40) return 'bg-orange-500 text-white';
    return 'bg-red-500 text-white';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  };

  const totalPages = Math.ceil(totalJobs / jobsPerPage);
  const isSearchInProgress = isSearching || taskStatus === 'running' || taskStatus === 'queued';

  const renderPagination = () => {
    if (totalPages <= 1) return null;

    return (
      <div className="flex items-center justify-center gap-2 mt-6">
        <button
          onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
          disabled={currentPage === 1}
          className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <span className="text-sm text-gray-600">
          Page {currentPage} of {totalPages}
        </span>
        <button
          onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
          disabled={currentPage === totalPages}
          className="p-2 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>
    );
  };

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
                Showing {jobs.length} of {totalJobs} job{totalJobs !== 1 ? 's' : ''}
                {isSearchInProgress && ' (searching...)'}
              </span>
            </div>
            <div className="space-y-4">
              {jobs.map((job) => {
                const isApplying = applyingJobs.has(job.id);
                const isTailoring = tailoringJobs.has(job.id);
                const isTailoringCoverLetter = tailoringCoverLetterJobs.has(job.id);
                const hasTailored = !!tailoredResumes[job.id];
                const isApplied = job.status === 'applied';
                const isQueued = !!applicationTasks[job.id];
                const score = matchScores[job.id] ?? job.match_score;
                const isCalculatingScore = calculatingScores.has(job.id);

                return (
                  <div key={job.id} className="card hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-start gap-3">
                          <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                            <Briefcase className="h-5 w-5 text-linkedin-blue" />
                          </div>
                          <div className="flex-1">
                            <div className="flex items-start gap-3">
                              <h3 className="font-semibold text-gray-900">{job.title}</h3>
                              {/* Match Score Badge */}
                              {score !== undefined && score !== null && (
                                <span className={clsx(
                                  'px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1',
                                  getMatchScoreColor(score)
                                )}>
                                  <Award className="h-3 w-3" />
                                  {score}% Match
                                </span>
                              )}
                              {isCalculatingScore && (
                                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500 flex items-center gap-1">
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                  Calculating...
                                </span>
                              )}
                            </div>
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

                    {/* Action Buttons */}
                    <div className="mt-4 pt-4 border-t border-gray-100 flex flex-wrap items-center gap-2">
                      {/* View Details Button */}
                      <button
                        onClick={() => setShowDetailsModal(job)}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
                      >
                        <Eye className="h-4 w-4" />
                        Details
                      </button>

                      {/* Tailor Resume Button */}
                      <button
                        onClick={() => handleTailor(job.id)}
                        disabled={isTailoring || !selectedResumeId}
                        className={clsx(
                          "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                          tailoredResumes[job.id]?.tailored_resume_text
                            ? "bg-green-100 text-green-700 hover:bg-green-200"
                            : "bg-purple-100 text-purple-700 hover:bg-purple-200"
                        )}
                      >
                        {isTailoring ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Tailoring...
                          </>
                        ) : tailoredResumes[job.id]?.tailored_resume_text ? (
                          <>
                            <CheckCircle className="h-4 w-4" />
                            <span onClick={(e) => {
                              e.stopPropagation();
                              setShowTailoredModal({ jobId: job.id, type: 'resume' });
                            }}>View Tailored Resume</span>
                          </>
                        ) : (
                          <>
                            <FileEdit className="h-4 w-4" />
                            Tailor Resume
                          </>
                        )}
                      </button>

                      {/* Tailored Cover Letter Button */}
                      <button
                        onClick={() => handleTailorCoverLetter(job.id)}
                        disabled={isTailoringCoverLetter || !selectedResumeId}
                        className={clsx(
                          "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
                          tailoredResumes[job.id]?.cover_letter
                            ? "bg-green-100 text-green-700 hover:bg-green-200"
                            : "bg-indigo-100 text-indigo-700 hover:bg-indigo-200"
                        )}
                      >
                        {isTailoringCoverLetter ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Generating...
                          </>
                        ) : tailoredResumes[job.id]?.cover_letter ? (
                          <>
                            <CheckCircle className="h-4 w-4" />
                            <span onClick={(e) => {
                              e.stopPropagation();
                              setShowTailoredModal({ jobId: job.id, type: 'cover_letter' });
                            }}>View Cover Letter</span>
                          </>
                        ) : (
                          <>
                            <FileSpreadsheet className="h-4 w-4" />
                            Tailored Cover Letter
                          </>
                        )}
                      </button>

                      {/* Apply Button - only for Easy Apply jobs not yet applied */}
                      {job.easy_apply && !isApplied && (
                        <button
                          onClick={() => setShowApplyModal(job.id)}
                          disabled={isApplying || isQueued}
                          className={clsx(
                            "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ml-auto",
                            isQueued
                              ? "bg-yellow-100 text-yellow-700"
                              : "bg-blue-600 text-white hover:bg-blue-700"
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
                      )}
                    </div>

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
            {renderPagination()}
          </>
        )}

        {/* Apply Modal */}
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

        {/* Job Details Modal */}
        {showDetailsModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">{showDetailsModal.title}</h2>
                    <p className="text-gray-600">{showDetailsModal.company}</p>
                  </div>
                  <button
                    onClick={() => setShowDetailsModal(null)}
                    className="p-2 hover:bg-gray-100 rounded-lg"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
                <div className="flex items-center gap-4 text-sm text-gray-500 mb-4">
                  <div className="flex items-center gap-1">
                    <MapPin className="h-4 w-4" />
                    {showDetailsModal.location}
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="h-4 w-4" />
                    {formatDate(showDetailsModal.discovered_at)}
                  </div>
                  {showDetailsModal.easy_apply && (
                    <div className="flex items-center gap-1 text-green-600">
                      <Zap className="h-4 w-4" />
                      Easy Apply
                    </div>
                  )}
                </div>
                {(matchScores[showDetailsModal.id] ?? showDetailsModal.match_score) && (
                  <div className="mb-4">
                    <span className={clsx(
                      'px-3 py-1 rounded-full text-sm font-medium inline-flex items-center gap-1',
                      getMatchScoreColor(matchScores[showDetailsModal.id] ?? showDetailsModal.match_score ?? 0)
                    )}>
                      <Award className="h-4 w-4" />
                      {(matchScores[showDetailsModal.id] ?? showDetailsModal.match_score)}% Match Score
                    </span>
                  </div>
                )}
                <div className="prose prose-sm max-w-none">
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Job Description</h3>
                  <div className="text-gray-600 whitespace-pre-wrap">
                    {showDetailsModal.description || 'No description available.'}
                  </div>
                </div>
                <div className="mt-6 flex gap-3">
                  <a
                    href={showDetailsModal.job_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex-1 btn-primary text-center"
                  >
                    View on LinkedIn
                  </a>
                  <button
                    onClick={() => setShowDetailsModal(null)}
                    className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg border"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tailored Content Modal */}
        {showTailoredModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg max-w-3xl w-full max-h-[90vh] overflow-y-auto">
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <h2 className="text-xl font-bold text-gray-900">
                    {showTailoredModal.type === 'resume' ? 'Tailored Resume' : 'Tailored Cover Letter'}
                  </h2>
                  <button
                    onClick={() => setShowTailoredModal(null)}
                    className="p-2 hover:bg-gray-100 rounded-lg"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
                <div className="prose prose-sm max-w-none bg-gray-50 p-4 rounded-lg">
                  <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans">
                    {showTailoredModal.type === 'resume'
                      ? tailoredResumes[showTailoredModal.jobId]?.tailored_resume_text
                      : tailoredResumes[showTailoredModal.jobId]?.cover_letter}
                  </pre>
                </div>
                <div className="mt-4 flex gap-3">
                  <button
                    onClick={() => {
                      const text = showTailoredModal.type === 'resume'
                        ? tailoredResumes[showTailoredModal.jobId]?.tailored_resume_text
                        : tailoredResumes[showTailoredModal.jobId]?.cover_letter;
                      navigator.clipboard.writeText(text || '');
                      toast.success('Copied to clipboard!');
                    }}
                    className="flex-1 btn-primary"
                  >
                    Copy to Clipboard
                  </button>
                  <button
                    onClick={() => setShowTailoredModal(null)}
                    className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg border"
                  >
                    Close
                  </button>
                </div>
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
