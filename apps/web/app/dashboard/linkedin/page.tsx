'use client';

import { useState, useEffect } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { linkedinApi } from '@/lib/api';
import { Link, ExternalLink, CheckCircle, XCircle, AlertCircle, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import clsx from 'clsx';

export default function LinkedInPage() {
  const [status, setStatus] = useState<{
    connected: boolean;
    status: string;
    last_validated?: string;
    expires_at?: string;
    message?: string;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [cookieValue, setCookieValue] = useState('');
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    setIsLoading(true);
    try {
      const data = await linkedinApi.getStatus();
      setStatus(data);
      setShowForm(!data.connected);
    } catch (error) {
      console.error('Failed to load LinkedIn status:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!cookieValue.trim()) {
      toast.error('Please enter your LinkedIn session cookie');
      return;
    }

    setIsLoading(true);
    try {
      await linkedinApi.saveSession(cookieValue.trim());
      toast.success('LinkedIn session saved successfully!');
      setCookieValue('');
      setShowForm(false);
      await loadStatus();
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to save session';
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleValidate = async () => {
    setIsValidating(true);
    try {
      const data = await linkedinApi.validate();
      setStatus(data);
      if (data.connected) {
        toast.success('LinkedIn session is valid!');
      } else {
        toast.error('LinkedIn session is invalid or expired');
      }
    } catch (error: any) {
      toast.error('Failed to validate session');
    } finally {
      setIsValidating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete your LinkedIn session?')) {
      return;
    }

    setIsLoading(true);
    try {
      await linkedinApi.deleteSession();
      toast.success('LinkedIn session deleted');
      setStatus({ connected: false, status: 'not_set' });
      setShowForm(true);
    } catch (error) {
      toast.error('Failed to delete session');
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = (s: string) => {
    switch (s) {
      case 'connected':
        return 'text-green-600 bg-green-100';
      case 'expired':
        return 'text-yellow-600 bg-yellow-100';
      case 'invalid':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (s: string) => {
    switch (s) {
      case 'connected':
        return <CheckCircle className="h-5 w-5" />;
      case 'expired':
      case 'invalid':
        return <XCircle className="h-5 w-5" />;
      default:
        return <AlertCircle className="h-5 w-5" />;
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  return (
    <DashboardLayout>
      <div className="page-container">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">LinkedIn Connection</h1>
          <p className="text-gray-600">Manage your LinkedIn session for job search and applications</p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-linkedin-blue"></div>
          </div>
        ) : (
          <>
            {/* Status Card */}
            {status && !showForm && (
              <div className="card mb-6">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className={clsx(
                      "w-12 h-12 rounded-lg flex items-center justify-center",
                      getStatusColor(status.status)
                    )}>
                      {getStatusIcon(status.status)}
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-gray-900">
                        LinkedIn Session
                      </h2>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={clsx(
                          "px-2 py-0.5 rounded-full text-xs font-medium capitalize",
                          getStatusColor(status.status)
                        )}>
                          {status.status.replace('_', ' ')}
                        </span>
                        {status.last_validated && (
                          <span className="text-sm text-gray-500">
                            Last validated: {formatDate(status.last_validated)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleValidate}
                      disabled={isValidating}
                      className="btn-secondary flex items-center gap-2"
                    >
                      {isValidating ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Validating...
                        </>
                      ) : (
                        <>
                          <CheckCircle className="h-4 w-4" />
                          Validate
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => setShowForm(true)}
                      className="btn-secondary"
                    >
                      Update
                    </button>
                    <button
                      onClick={handleDelete}
                      className="px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Setup/Update Form */}
            {showForm && (
              <div className="card">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">
                  {status?.connected ? 'Update' : 'Connect'} LinkedIn Session
                </h2>
                
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                  <h3 className="font-medium text-blue-900 mb-2">How to get your LinkedIn session cookie:</h3>
                  <ol className="list-decimal list-inside text-sm text-blue-800 space-y-1">
                    <li>Log in to LinkedIn in your browser</li>
                    <li>Open Developer Tools (F12 or Cmd+Option+I)</li>
                    <li>Go to Application/Storage → Cookies → linkedin.com</li>
                    <li>Find the cookie named <code className="bg-blue-100 px-1 rounded">li_at</code></li>
                    <li>Copy its value and paste it below</li>
                  </ol>
                  <div className="mt-3 flex items-start gap-2">
                    <AlertCircle className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-blue-800">
                      Your session cookie is encrypted and stored securely. We never store your LinkedIn password.
                    </p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                    LinkedIn Session Cookie (li_at)
                  </label>
                  <textarea
                    value={cookieValue}
                    onChange={(e) => setCookieValue(e.target.value)}
                    placeholder="Paste your li_at cookie value here..."
                    rows={4}
                    className="input-field font-mono text-sm"
                  />
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={handleSave}
                    disabled={isLoading || !cookieValue.trim()}
                    className="btn-primary flex items-center gap-2"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Saving...
                      </>
                    ) : (
                      <>
                        <Link className="h-4 w-4" />
                        Connect LinkedIn
                      </>
                    )}
                  </button>
                  {status?.connected && (
                    <button
                      onClick={() => setShowForm(false)}
                      className="btn-secondary"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>

                <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <h4 className="font-medium text-yellow-900 mb-2">Important Notes:</h4>
                  <ul className="text-sm text-yellow-800 space-y-1">
                    <li>• LinkedIn sessions typically expire after 90 days of inactivity</li>
                    <li>• Keep your session active by visiting LinkedIn regularly</li>
                    <li>• If your session expires, you'll need to re-connect</li>
                    <li>• We never access your LinkedIn password or credentials</li>
                  </ul>
                </div>
              </div>
            )}
          </>
        )}

        {/* Help Section */}
        <div className="mt-8 card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">How It Works</h2>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-3">
                <Link className="h-6 w-6 text-linkedin-blue" />
              </div>
              <h3 className="font-medium text-gray-900 mb-1">1. Connect</h3>
              <p className="text-sm text-gray-600">
                Provide your LinkedIn session cookie to enable automation
              </p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-3">
                <ExternalLink className="h-6 w-6 text-linkedin-blue" />
              </div>
              <h3 className="font-medium text-gray-900 mb-1">2. Search Jobs</h3>
              <p className="text-sm text-gray-600">
                We search LinkedIn for jobs matching your criteria
              </p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mx-auto mb-3">
                <CheckCircle className="h-6 w-6 text-linkedin-blue" />
              </div>
              <h3 className="font-medium text-gray-900 mb-1">3. Apply</h3>
              <p className="text-sm text-gray-600">
                Apply to Easy Apply jobs automatically with tailored resumes
              </p>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
