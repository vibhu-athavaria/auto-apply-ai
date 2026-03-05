'use client';

import { Search, Briefcase, MapPin, CheckCircle, AlertCircle } from 'lucide-react';

interface ProfileData {
  profileName: string;
  keywords: string;
  location: string;
  experienceLevel: string;
  jobType: string;
  remoteOnly: boolean;
}

interface ProfileStepProps {
  data: ProfileData;
  onChange: (data: Partial<ProfileData>) => void;
  resumeStatus: 'pending' | 'complete';
  linkedinStatus: 'pending' | 'complete' | 'skipped';
}

const EXPERIENCE_LEVELS = [
  { value: 'entry', label: 'Entry Level' },
  { value: 'mid', label: 'Mid Level' },
  { value: 'senior', label: 'Senior Level' },
  { value: 'executive', label: 'Executive' },
];

const JOB_TYPES = [
  { value: 'full-time', label: 'Full-time' },
  { value: 'part-time', label: 'Part-time' },
  { value: 'contract', label: 'Contract' },
  { value: 'internship', label: 'Internship' },
];

export default function ProfileStep({
  data,
  onChange,
  resumeStatus,
  linkedinStatus,
}: ProfileStepProps) {
  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Search className="h-8 w-8 text-linkedin-blue" />
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Create Job Search Profile</h2>
        <p className="text-gray-600 mt-2">Define your job preferences to find matching opportunities</p>
      </div>

      <div className="card">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Profile Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={data.profileName}
              onChange={(e) => onChange({ profileName: e.target.value })}
              className="input-field"
              placeholder="e.g., Software Engineer Search"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              <div className="flex items-center gap-2">
                <Briefcase className="h-4 w-4" />
                Keywords <span className="text-red-500">*</span>
              </div>
            </label>
            <input
              type="text"
              value={data.keywords}
              onChange={(e) => onChange({ keywords: e.target.value })}
              className="input-field"
              placeholder="e.g., Software Engineer, Python Developer"
            />
            <p className="text-xs text-gray-500 mt-1">
              Job titles, skills, or keywords to search for
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4" />
                Location <span className="text-red-500">*</span>
              </div>
            </label>
            <input
              type="text"
              value={data.location}
              onChange={(e) => onChange({ location: e.target.value })}
              className="input-field"
              placeholder="e.g., San Francisco, CA or Remote"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Experience Level
              </label>
              <select
                value={data.experienceLevel}
                onChange={(e) => onChange({ experienceLevel: e.target.value })}
                className="input-field"
              >
                <option value="">Any Level</option>
                {EXPERIENCE_LEVELS.map((level) => (
                  <option key={level.value} value={level.value}>
                    {level.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Job Type</label>
              <select
                value={data.jobType}
                onChange={(e) => onChange({ jobType: e.target.value })}
                className="input-field"
              >
                <option value="">Any Type</option>
                {JOB_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <input
              type="checkbox"
              id="remote-only"
              checked={data.remoteOnly}
              onChange={(e) => onChange({ remoteOnly: e.target.checked })}
              className="h-4 w-4 text-linkedin-blue focus:ring-linkedin-blue border-gray-300 rounded"
            />
            <label htmlFor="remote-only" className="text-sm text-gray-700">
              Remote Only
            </label>
          </div>
        </div>
      </div>

      {/* Summary Card */}
      <div className="card bg-gray-50">
        <h3 className="font-semibold text-gray-900 mb-4">Profile Summary</h3>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">Resume:</span>
            <span className={resumeStatus === 'complete' ? 'text-green-600' : 'text-red-600'}>
              {resumeStatus === 'complete' ? '✓ Uploaded' : '✗ Missing'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">LinkedIn:</span>
            <span
              className={
                linkedinStatus === 'complete'
                  ? 'text-green-600'
                  : linkedinStatus === 'skipped'
                    ? 'text-yellow-600'
                    : 'text-red-600'
              }
            >
              {linkedinStatus === 'complete'
                ? '✓ Connected'
                : linkedinStatus === 'skipped'
                  ? '⚠ Skipped'
                  : '✗ Not connected'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Profile Name:</span>
            <span className="text-gray-900">
              {data.profileName || <em className="text-gray-400">Not set</em>}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Keywords:</span>
            <span className="text-gray-900">
              {data.keywords || <em className="text-gray-400">Not set</em>}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Location:</span>
            <span className="text-gray-900">
              {data.location || <em className="text-gray-400">Not set</em>}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
