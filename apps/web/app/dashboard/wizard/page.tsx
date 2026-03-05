'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/DashboardLayout';
import { profileApi } from '@/lib/api';
import { CheckCircle, AlertCircle, Loader2, ChevronRight, ChevronLeft } from 'lucide-react';
import toast from 'react-hot-toast';

import ResumeStep from '@/components/wizard/ResumeStep';
import LinkedInStep from '@/components/wizard/LinkedInStep';
import ProfileStep from '@/components/wizard/ProfileStep';
import { useLinkedInConnection } from '@/hooks/useLinkedInConnection';

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

export default function WizardPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [wizardData, setWizardData] = useState<WizardData>(INITIAL_DATA);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // LinkedIn connection hook
  const linkedin = useLinkedInConnection(
    useCallback(() => {
      setWizardData((prev) => ({ ...prev, linkedinConnected: true }));
    }, []),
    useCallback(() => {
      setWizardData((prev) => ({ ...prev, linkedinSkipped: true }));
    }, [])
  );

  // Step 1: Resume Upload Handlers
  const handleResumeUpload = useCallback((filename: string) => {
    setWizardData((prev) => ({
      ...prev,
      resumeUploaded: true,
      resumeFilename: filename,
    }));
  }, []);

  const handleResumeChange = useCallback(() => {
    setWizardData((prev) => ({
      ...prev,
      resumeUploaded: false,
      resumeFilename: '',
    }));
  }, []);

  // Step 3: Profile Update Handler
  const handleProfileChange = useCallback((data: Partial<WizardData>) => {
    setWizardData((prev) => ({ ...prev, ...data }));
  }, []);

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
      await profileApi.create({
        keywords: wizardData.keywords,
        location: wizardData.location,
        remote_preference: wizardData.remoteOnly ? 'remote' : 'hybrid',
        experience_level: wizardData.experienceLevel || undefined,
        job_type: wizardData.jobType || undefined,
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
  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return (
          <ResumeStep
            isUploaded={wizardData.resumeUploaded}
            filename={wizardData.resumeFilename}
            onUploadComplete={handleResumeUpload}
            onChange={handleResumeChange}
          />
        );
      case 2:
        return (
          <LinkedInStep
            isConnected={wizardData.linkedinConnected}
            isSkipped={wizardData.linkedinSkipped}
            email={linkedin.email}
            password={linkedin.password}
            showPassword={linkedin.showPassword}
            status={linkedin.status}
            message={linkedin.message}
            showSkipWarning={linkedin.showSkipWarning}
            onEmailChange={linkedin.setEmail}
            onPasswordChange={linkedin.setPassword}
            onTogglePassword={() => linkedin.setShowPassword(!linkedin.showPassword)}
            onConnect={() => linkedin.connect(linkedin.email, linkedin.password)}
            onSkip={linkedin.skip}
            onConfirmSkip={linkedin.confirmSkip}
            onCancelSkip={() => linkedin.setShowSkipWarning(false)}
            onRetry={() => {
              linkedin.reset();
              setWizardData((prev) => ({ ...prev, linkedinSkipped: false }));
            }}
          />
        );
      case 3:
        return (
          <ProfileStep
            data={{
              profileName: wizardData.profileName,
              keywords: wizardData.keywords,
              location: wizardData.location,
              experienceLevel: wizardData.experienceLevel,
              jobType: wizardData.jobType,
              remoteOnly: wizardData.remoteOnly,
            }}
            onChange={handleProfileChange}
            resumeStatus={wizardData.resumeUploaded ? 'complete' : 'pending'}
            linkedinStatus={
              wizardData.linkedinConnected
                ? 'complete'
                : wizardData.linkedinSkipped
                  ? 'skipped'
                  : 'pending'
            }
          />
        );
      default:
        return null;
    }
  };

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
        <div className="mb-8">{renderStep()}</div>

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
