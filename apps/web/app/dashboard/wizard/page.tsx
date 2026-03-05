'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useDropzone } from 'react-dropzone';
import DashboardLayout from '@/components/DashboardLayout';
import { resumeApi, linkedinApi, profileApi } from '@/lib/api';
import {
  FileText,
  Upload,
  Link,
  CheckCircle,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  Briefcase,
  MapPin,
  ChevronRight,
  ChevronLeft,
  Search,
  ShieldAlert,
} from 'lucide-react';
import toast from 'react-hot-toast';

// Types
interface WizardData {
  resumeUploaded: boolean;
  resumeFilename: string;
  linkedinConnected: boolean;
  linkedinSkipped: boolean;
  profileName: string;
  keywords: string;
  location: string;
  experienceLevel: string;
  jobType: string;
  remoteOnly: boolean;
}

type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'failed' | 'skipped';
type StepStatus = 'pending' | 'complete' | 'skipped';

const INITIAL_DATA: WizardData = {
  resumeUploaded: false,
  resumeFilename: '',
  linkedinConnected: false,
  linkedinSkipped: false,
  profileName: '',
  keywords: '',
  location: '',
  experienceLevel: '',
  jobType: '',
  remoteOnly: false,
};

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

export default function WizardPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [wizardData, setWizardData] = useState<WizardData>(INITIAL_DATA);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Step 1: Resume Upload State
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Step 2: LinkedIn Connection State
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('idle');
  const [connectingTaskId, setConnectingTaskId] = useState<string | null>(null);
  const [connectionMessage, setConnectionMessage] = useState('');
  const [showSkipWarning, setShowSkipWarning] = useState(false);

  // Poll LinkedIn connection status
  useEffect(() => {
    if (!connectingTaskId) return;

    const interval = setInterval(async () => {
      try {
        const taskStatus = await linkedinApi.getConnectStatus(connectingTaskId);

        if (taskStatus.status === 'connected') {
          clearInterval(interval);
          setConnectingTaskId(null);
          setConnectionStatus('connected');
          setConnectionMessage('LinkedIn connected successfully!');
          setWizardData((prev: WizardData) => ({ ...prev, linkedinConnected: true }));
          toast.success('LinkedIn connected successfully!');
        } else if (taskStatus.status === 'failed') {
          clearInterval(interval);
          setConnectingTaskId(null);
          setConnectionStatus('failed');
          setConnectionMessage(taskStatus.message || 'Connection failed');
          toast.error(taskStatus.message || 'Connection failed');
        } else if (taskStatus.status === 'challenge_required') {
          clearInterval(interval);
          setConnectingTaskId(null);
          setConnectionStatus('failed');
          setConnectionMessage('LinkedIn requires verification. Please check your email or phone.');
          toast.error('LinkedIn requires verification');
        } else {
          setConnectionMessage('Connecting to LinkedIn...');
        }
      } catch {
        clearInterval(interval);
        setConnectingTaskId(null);
        setConnectionStatus('failed');
        setConnectionMessage('Failed to check connection status');
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [connectingTaskId]);

  // Step 1: Resume Upload Handlers
  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    // Validate file type
    const validTypes = [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ];
    if (!validTypes.includes(file.type)) {
      setUploadError('Invalid file type. Please upload PDF, DOC, or DOCX files only.');
      return;
    }

    // Validate file size (max 5MB)
    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
      setUploadError('File too large. Maximum size is 5MB.');
      return;
    }

    setIsUploading(true);
    setUploadError(null);

    try {
      await resumeApi.upload(file);
      setWizardData((prev: WizardData) => ({
        ...prev,
        resumeUploaded: true,
        resumeFilename: file.name,
      }));
      toast.success('Resume uploaded successfully!');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to upload resume';
      setUploadError(message);
      toast.error(message);
    } finally {
      setIsUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/msword': ['.doc'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxSize: 5 * 1024 * 1024, // 5MB
    multiple: false,
  });

  // Step 2: LinkedIn Connection Handlers
  const handleConnect = async () => {
    if (!email.trim() || !password.trim()) {
      toast.error('Please enter your LinkedIn email and password');
      return;
    }

    setConnectionStatus('connecting');
    setConnectionMessage('Starting connection...');

    try {
      const result = await linkedinApi.connect(email, password);
      setConnectingTaskId(result.task_id);
      setConnectionMessage('Connecting to LinkedIn...');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to start connection';
      setConnectionStatus('failed');
      setConnectionMessage(message);
      toast.error(message);
    }
  };

  const handleSkipLinkedIn = () => {
    setShowSkipWarning(true);
  };

  const confirmSkipLinkedIn = () => {
    setConnectionStatus('skipped');
    setWizardData((prev: WizardData) => ({ ...prev, linkedinSkipped: true }));
    setShowSkipWarning(false);
    toast('LinkedIn connection skipped. You can connect later.', { icon: '⚠️' });
  };

  // Step 3: Profile Creation Handler
  const handleCreateProfile = async () => {
    // Validate required fields
    if (!wizardData.profileName.trim()) {
      toast.error('Profile name is required');
      return;
    }
    if (!wizardData.keywords.trim()) {
      toast.error('Keywords are required');
      return;
    }
    if (!wizardData.location.trim()) {
      toast.error('Location is required');
      return;
    }

    setIsSubmitting(true);

    try {
      // Build keywords string with experience level and job type
      let keywords = wizardData.keywords;
      if (wizardData.experienceLevel) {
        const levelLabel = EXPERIENCE_LEVELS.find(
          (l) => l.value === wizardData.experienceLevel
        )?.label;
        if (levelLabel) {
          keywords += ` (${levelLabel})`;
        }
      }
      if (wizardData.jobType) {
        const typeLabel = JOB_TYPES.find((t) => t.value === wizardData.jobType)?.label;
        if (typeLabel) {
          keywords += ` - ${typeLabel}`;
        }
      }

      await profileApi.create({
        keywords,
        location: wizardData.location,
      });

      toast.success('Job search profile created successfully!');
      router.push('/dashboard/profiles');
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to create profile';
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Navigation Handlers
  const canProceedToNext = () => {
    switch (currentStep) {
      case 1:
        return wizardData.resumeUploaded;
      case 2:
        return wizardData.linkedinConnected || wizardData.linkedinSkipped;
      case 3:
        return true;
      default:
        return false;
    }
  };

  const handleNext = () => {
    if (currentStep < 3) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  // Render Step Content
  const renderStep1 = () => (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <FileText className="h-8 w-8 text-linkedin-blue" />
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Upload Your Resume</h2>
        <p className="text-gray-600 mt-2">Upload your resume so we can tailor your applications</p>
      </div>

      {!wizardData.resumeUploaded ? (
        <div className="card">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-linkedin-blue bg-blue-50'
                : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            {isUploading ? (
              <div className="flex items-center justify-center gap-2">
                <Loader2 className="animate-spin h-5 w-5 text-linkedin-blue" />
                <span className="text-gray-600">Uploading...</span>
              </div>
            ) : isDragActive ? (
              <p className="text-linkedin-blue font-medium">Drop your resume here...</p>
            ) : (
              <div>
                <p className="text-gray-700 font-medium mb-1">
                  Drag and drop your resume here, or click to browse
                </p>
                <p className="text-sm text-gray-500">Supports PDF, DOC, DOCX (max 5MB)</p>
              </div>
            )}
          </div>

          {uploadError && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
              <p className="text-sm text-red-700">{uploadError}</p>
            </div>
          )}

          {fileRejections.length > 0 && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">
                {fileRejections[0].errors[0].code === 'file-too-large'
                  ? 'File too large. Maximum size is 5MB.'
                  : 'Invalid file type. Please upload PDF, DOC, or DOCX files only.'}
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="card bg-green-50 border-green-200">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle className="h-6 w-6 text-green-600" />
            </div>
            <div className="flex-1">
              <p className="font-medium text-gray-900">Resume Uploaded</p>
              <p className="text-sm text-gray-600">{wizardData.resumeFilename}</p>
            </div>
            <button
              onClick={() =>
                setWizardData((prev: WizardData) => ({
                  ...prev,
                  resumeUploaded: false,
                  resumeFilename: '',
                }))
              }
              className="text-sm text-gray-500 hover:text-gray-700"
            >
              Change
            </button>
          </div>
        </div>
      )}
    </div>
  );

  const renderStep2 = () => (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Link className="h-8 w-8 text-linkedin-blue" />
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Connect LinkedIn</h2>
        <p className="text-gray-600 mt-2">Connect your LinkedIn account to enable job applications</p>
      </div>

      {connectionStatus === 'connected' || wizardData.linkedinConnected ? (
        <div className="card bg-green-50 border-green-200">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
              <CheckCircle className="h-6 w-6 text-green-600" />
            </div>
            <div>
              <p className="font-semibold text-gray-900">LinkedIn Connected</p>
              <p className="text-sm text-gray-600">Your account is ready for job applications</p>
            </div>
          </div>
        </div>
      ) : connectionStatus === 'skipped' || wizardData.linkedinSkipped ? (
        <div className="card bg-yellow-50 border-yellow-200">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-yellow-100 rounded-full flex items-center justify-center">
              <AlertCircle className="h-6 w-6 text-yellow-600" />
            </div>
            <div className="flex-1">
              <p className="font-semibold text-gray-900">LinkedIn Skipped</p>
              <p className="text-sm text-gray-600">
                You can connect your LinkedIn account later from the settings
              </p>
            </div>
            <button
              onClick={() => {
                setConnectionStatus('idle');
                setWizardData((prev: WizardData) => ({ ...prev, linkedinSkipped: false }));
              }}
              className="text-sm text-linkedin-blue hover:text-linkedin-dark"
            >
              Connect Now
            </button>
          </div>
        </div>
      ) : (
        <div className="card">
          {/* 2FA Notice */}
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex gap-3">
              <AlertCircle className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-blue-900">Two-Factor Authentication</p>
                <p className="text-sm text-blue-700 mt-1">
                  You may need to authenticate on a secondary device if 2FA is enabled on your
                  LinkedIn account. Check your phone or email for verification codes.
                </p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                LinkedIn Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="input-field"
                disabled={connectionStatus === 'connecting'}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                LinkedIn Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Your LinkedIn password"
                  className="input-field pr-10"
                  disabled={connectionStatus === 'connecting'}
                  onKeyDown={(e) => e.key === 'Enter' && handleConnect()}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {connectionStatus === 'failed' && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-700">{connectionMessage}</p>
              </div>
            )}

            <button
              onClick={handleConnect}
              disabled={connectionStatus === 'connecting' || !email || !password}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {connectionStatus === 'connecting' ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {connectionMessage || 'Connecting...'}
                </>
              ) : (
                <>
                  <Link className="h-4 w-4" />
                  Connect LinkedIn
                </>
              )}
            </button>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">or</span>
              </div>
            </div>

            <button
              onClick={handleSkipLinkedIn}
              disabled={connectionStatus === 'connecting'}
              className="btn-secondary w-full"
            >
              Skip for Now
            </button>
          </div>

          <p className="mt-4 text-xs text-gray-500 text-center">
            Your password is used once to log in and is <strong>never stored</strong>. Only the
            session token is saved (encrypted).
          </p>
        </div>
      )}

      {/* Skip Warning Modal */}
      {showSkipWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black bg-opacity-50" onClick={() => setShowSkipWarning(false)} />
          <div className="relative bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-yellow-100 rounded-full flex items-center justify-center">
                <ShieldAlert className="h-5 w-5 text-yellow-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Skip LinkedIn Connection?</h3>
            </div>
            <p className="text-gray-600 mb-6">
              Without LinkedIn connected, you won't be able to search for jobs or submit
              applications. You can always connect later from the settings.
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowSkipWarning(false)}
                className="btn-secondary flex-1"
              >
                Go Back
              </button>
              <button onClick={confirmSkipLinkedIn} className="btn-primary flex-1">
                Skip Anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderStep3 = () => (
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
              value={wizardData.profileName}
              onChange={(e) =>
                setWizardData((prev: WizardData) => ({ ...prev, profileName: e.target.value }))
              }
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
              value={wizardData.keywords}
              onChange={(e) =>
                setWizardData((prev: WizardData) => ({ ...prev, keywords: e.target.value }))
              }
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
              value={wizardData.location}
              onChange={(e) =>
                setWizardData((prev: WizardData) => ({ ...prev, location: e.target.value }))
              }
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
                value={wizardData.experienceLevel}
                onChange={(e) =>
                  setWizardData((prev: WizardData) => ({ ...prev, experienceLevel: e.target.value }))
                }
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
                value={wizardData.jobType}
                onChange={(e) =>
                  setWizardData((prev: WizardData) => ({ ...prev, jobType: e.target.value }))
                }
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
              checked={wizardData.remoteOnly}
              onChange={(e) =>
                setWizardData((prev: WizardData) => ({ ...prev, remoteOnly: e.target.checked }))
              }
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
            <span className={wizardData.resumeUploaded ? 'text-green-600' : 'text-red-600'}>
              {wizardData.resumeUploaded ? '✓ Uploaded' : '✗ Missing'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">LinkedIn:</span>
            <span
              className={
                wizardData.linkedinConnected
                  ? 'text-green-600'
                  : wizardData.linkedinSkipped
                    ? 'text-yellow-600'
                    : 'text-red-600'
              }
            >
              {wizardData.linkedinConnected
                ? '✓ Connected'
                : wizardData.linkedinSkipped
                  ? '⚠ Skipped'
                  : '✗ Not connected'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Profile Name:</span>
            <span className="text-gray-900">
              {wizardData.profileName || <em className="text-gray-400">Not set</em>}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Keywords:</span>
            <span className="text-gray-900">
              {wizardData.keywords || <em className="text-gray-400">Not set</em>}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Location:</span>
            <span className="text-gray-900">
              {wizardData.location || <em className="text-gray-400">Not set</em>}
            </span>
          </div>
        </div>
      </div>
    </div>
  );

  // Progress Step Component
  const StepIndicator = ({
    step,
    label,
    status,
  }: {
    step: number;
    label: string;
    status: StepStatus;
  }) => (
    <div className="flex flex-col items-center">
      <div
        className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-colors ${
          currentStep === step
            ? 'bg-linkedin-blue text-white'
            : status === 'complete'
              ? 'bg-green-500 text-white'
              : status === 'skipped'
                ? 'bg-yellow-500 text-white'
                : 'bg-gray-200 text-gray-600'
        }`}
      >
        {status === 'complete' ? (
          <CheckCircle className="h-5 w-5" />
        ) : status === 'skipped' ? (
          <AlertCircle className="h-5 w-5" />
        ) : (
          step
        )}
      </div>
      <span
        className={`text-xs mt-2 font-medium ${
          currentStep === step ? 'text-linkedin-blue' : 'text-gray-500'
        }`}
      >
        {label}
      </span>
    </div>
  );

  const getStepStatus = (step: number): StepStatus => {
    switch (step) {
      case 1:
        return wizardData.resumeUploaded ? 'complete' : 'pending';
      case 2:
        if (wizardData.linkedinConnected) return 'complete';
        if (wizardData.linkedinSkipped) return 'skipped';
        return 'pending';
      case 3:
        return 'pending';
      default:
        return 'pending';
    }
  };

  return (
    <DashboardLayout>
      <div className="page-container max-w-2xl">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-gray-900">Create Job Search Profile</h1>
          <p className="text-gray-600 mt-2">
            Complete these steps to start finding your next opportunity
          </p>
        </div>

        {/* Progress Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <StepIndicator step={1} label="Resume" status={getStepStatus(1)} />
            <div
              className={`flex-1 h-1 mx-4 ${currentStep > 1 ? 'bg-green-500' : 'bg-gray-200'}`}
            />
            <StepIndicator step={2} label="LinkedIn" status={getStepStatus(2)} />
            <div
              className={`flex-1 h-1 mx-4 ${currentStep > 2 ? 'bg-green-500' : 'bg-gray-200'}`}
            />
            <StepIndicator step={3} label="Profile" status={getStepStatus(3)} />
          </div>
        </div>

        {/* Step Content */}
        <div className="mb-8">
          {currentStep === 1 && renderStep1()}
          {currentStep === 2 && renderStep2()}
          {currentStep === 3 && renderStep3()}
        </div>

        {/* Navigation Buttons */}
        <div className="flex justify-between">
          <button
            onClick={handlePrevious}
            disabled={currentStep === 1}
            className="btn-secondary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </button>

          {currentStep < 3 ? (
            <button
              onClick={handleNext}
              disabled={!canProceedToNext()}
              className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={handleCreateProfile}
              disabled={isSubmitting}
              className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <CheckCircle className="h-4 w-4" />
                  Create Profile
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
