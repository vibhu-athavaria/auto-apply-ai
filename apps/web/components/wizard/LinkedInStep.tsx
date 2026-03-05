'use client';

import { Link, CheckCircle, AlertCircle, Loader2, Eye, EyeOff, ShieldAlert } from 'lucide-react';

type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'failed' | 'skipped';

interface LinkedInStepProps {
  isConnected: boolean;
  isSkipped: boolean;
  email: string;
  password: string;
  showPassword: boolean;
  status: ConnectionStatus;
  message: string;
  showSkipWarning: boolean;
  onEmailChange: (email: string) => void;
  onPasswordChange: (password: string) => void;
  onTogglePassword: () => void;
  onConnect: () => void;
  onSkip: () => void;
  onConfirmSkip: () => void;
  onCancelSkip: () => void;
  onRetry: () => void;
}

export default function LinkedInStep({
  isConnected,
  isSkipped,
  email,
  password,
  showPassword,
  status,
  message,
  showSkipWarning,
  onEmailChange,
  onPasswordChange,
  onTogglePassword,
  onConnect,
  onSkip,
  onConfirmSkip,
  onCancelSkip,
  onRetry,
}: LinkedInStepProps) {
  if (isConnected || status === 'connected') {
    return (
      <div className="space-y-6">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Link className="h-8 w-8 text-linkedin-blue" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">Connect LinkedIn</h2>
          <p className="text-gray-600 mt-2">Connect your LinkedIn account to enable job applications</p>
        </div>

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
      </div>
    );
  }

  if (isSkipped || status === 'skipped') {
    return (
      <div className="space-y-6">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Link className="h-8 w-8 text-linkedin-blue" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">Connect LinkedIn</h2>
          <p className="text-gray-600 mt-2">Connect your LinkedIn account to enable job applications</p>
        </div>

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
              onClick={onRetry}
              className="text-sm text-linkedin-blue hover:text-linkedin-dark"
            >
              Connect Now
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Link className="h-8 w-8 text-linkedin-blue" />
        </div>
        <h2 className="text-xl font-semibold text-gray-900">Connect LinkedIn</h2>
        <p className="text-gray-600 mt-2">Connect your LinkedIn account to enable job applications</p>
      </div>

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
              onChange={(e) => onEmailChange(e.target.value)}
              placeholder="you@example.com"
              className="input-field"
              disabled={status === 'connecting'}
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
                onChange={(e) => onPasswordChange(e.target.value)}
                placeholder="Your LinkedIn password"
                className="input-field pr-10"
                disabled={status === 'connecting'}
                onKeyDown={(e) => e.key === 'Enter' && onConnect()}
              />
              <button
                type="button"
                onClick={onTogglePassword}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          {status === 'failed' && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">{message}</p>
            </div>
          )}

          <button
            onClick={onConnect}
            disabled={status === 'connecting' || !email || !password}
            className="btn-primary w-full flex items-center justify-center gap-2"
          >
            {status === 'connecting' ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {message || 'Connecting...'}
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
            onClick={onSkip}
            disabled={status === 'connecting'}
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

      {/* Skip Warning Modal */}
      {showSkipWarning && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black bg-opacity-50" onClick={onCancelSkip} />
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
              <button onClick={onCancelSkip} className="btn-secondary flex-1">
                Go Back
              </button>
              <button onClick={onConfirmSkip} className="btn-primary flex-1">
                Skip Anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
