'use client';

import { useState, useEffect } from 'react';
import DashboardLayout from '@/components/DashboardLayout';
import { linkedinApi } from '@/lib/api';
import { Link, ExternalLink, CheckCircle, XCircle, AlertCircle, Loader2, Eye, EyeOff } from 'lucide-react';
import toast from 'react-hot-toast';
import clsx from 'clsx';

type ConnectionStatus = {
  connected: boolean;
  status: string;
  last_validated?: string;
  expires_at?: string;
  message?: string;
};

export default function LinkedInPage() {
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectingTaskId, setConnectingTaskId] = useState<string | null>(null);
  const [connectMessage, setConnectMessage] = useState('');

  useEffect(() => {
    loadStatus();
  }, []);

  // Poll task status while connecting
  useEffect(() => {
    if (!connectingTaskId) return;

    const interval = setInterval(async () => {
      try {
        const taskStatus = await linkedinApi.getConnectStatus(connectingTaskId);

        if (taskStatus.status === 'connected') {
          clearInterval(interval);
          setConnectingTaskId(null);
          setIsConnecting(false);
          setEmail('');
          setPassword('');
          toast.success('LinkedIn connected successfully!');
          await loadStatus();
        } else if (taskStatus.status === 'failed') {
          clearInterval(interval);
          setConnectingTaskId(null);
          setIsConnecting(false);
          toast.error(taskStatus.message || 'Connection failed');
          setConnectMessage('');
        } else if (taskStatus.status === 'challenge_required') {
          clearInterval(interval);
          setConnectingTaskId(null);
          setIsConnecting(false);
          toast.error(taskStatus.message || 'LinkedIn requires verification');
          setConnectMessage('');
        } else {
          setConnectMessage('Logging in to LinkedIn...');
        }
      } catch {
        clearInterval(interval);
        setConnectingTaskId(null);
        setIsConnecting(false);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [connectingTaskId]);

  const loadStatus = async () => {
    setIsLoading(true);
    try {
      const data = await linkedinApi.getStatus();
      setStatus(data);
    } catch {
      console.error('Failed to load LinkedIn status');
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnect = async () => {
    if (!email.trim() || !password.trim()) {
      toast.error('Please enter your LinkedIn email and password');
      return;
    }

    setIsConnecting(true);
    setConnectMessage('Starting connection...');

    try {
      const result = await linkedinApi.connect(email, password);
      setConnectingTaskId(result.task_id);
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Failed to start connection';
      toast.error(message);
      setIsConnecting(false);
      setConnectMessage('');
    }
  };

  const handleDisconnect = async () => {
    if (!confirm('Are you sure you want to disconnect your LinkedIn account?')) return;

    try {
      await linkedinApi.deleteSession();
      toast.success('LinkedIn disconnected');
      setStatus({ connected: false, status: 'not_set' });
    } catch {
      toast.error('Failed to disconnect');
    }
  };

  const handleValidate = async () => {
    setIsLoading(true);
    try {
      const data = await linkedinApi.validate();
      setStatus(data);
      toast[data.connected ? 'success' : 'error'](
        data.connected ? 'Session is valid!' : 'Session expired — please reconnect'
      );
    } catch {
      toast.error('Validation failed');
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = (s: string) =>
    ({ connected: 'text-green-600 bg-green-100', expired: 'text-yellow-600 bg-yellow-100', invalid: 'text-red-600 bg-red-100' }[s] ?? 'text-gray-600 bg-gray-100');

  const formatDate = (d?: string) => d ? new Date(d).toLocaleString() : '—';

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-linkedin-blue" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="page-container max-w-2xl">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900">LinkedIn Connection</h1>
          <p className="text-gray-600">Connect your LinkedIn account to enable job search and Easy Apply automation</p>
        </div>

        {/* Connected state */}
        {status?.connected ? (
          <div className="card mb-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
                  <CheckCircle className="h-6 w-6 text-green-600" />
                </div>
                <div>
                  <p className="font-semibold text-gray-900">LinkedIn Connected</p>
                  <p className="text-sm text-gray-500">
                    Last validated: {formatDate(status.last_validated)}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={handleValidate} className="btn-secondary text-sm py-1.5">
                  Validate
                </button>
                <button
                  onClick={handleDisconnect}
                  className="px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                >
                  Disconnect
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* Connect form */
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Connect LinkedIn Account</h2>
            <p className="text-sm text-gray-500 mb-6">
              Your password is used once to log in and is <strong>never stored</strong>. Only the resulting session token is saved (encrypted).
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">LinkedIn Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="input-field"
                  disabled={isConnecting}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">LinkedIn Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    placeholder="Your LinkedIn password"
                    className="input-field pr-10"
                    disabled={isConnecting}
                    onKeyDown={e => e.key === 'Enter' && handleConnect()}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <button
                onClick={handleConnect}
                disabled={isConnecting || !email || !password}
                className="btn-primary w-full flex items-center justify-center gap-2"
              >
                {isConnecting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {connectMessage || 'Connecting...'}
                  </>
                ) : (
                  <>
                    <Link className="h-4 w-4" />
                    Connect LinkedIn
                  </>
                )}
              </button>
            </div>

            <div className="mt-4 p-3 bg-blue-50 rounded-lg flex gap-2">
              <AlertCircle className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-blue-800">
                If LinkedIn requires a verification code (2FA), you will be notified. Log in to linkedin.com manually to resolve the challenge, then try again.
              </p>
            </div>
          </div>
        )}

        {/* How it works */}
        <div className="card mt-6">
          <h3 className="font-semibold text-gray-900 mb-4">How it works</h3>
          <ol className="space-y-3 text-sm text-gray-600">
            <li className="flex gap-3"><span className="font-bold text-linkedin-blue">1.</span> Enter your LinkedIn credentials above</li>
            <li className="flex gap-3"><span className="font-bold text-linkedin-blue">2.</span> We log in on your behalf using an automated browser (Playwright)</li>
            <li className="flex gap-3"><span className="font-bold text-linkedin-blue">3.</span> Your password is discarded immediately — only the session token is saved (encrypted)</li>
            <li className="flex gap-3"><span className="font-bold text-linkedin-blue">4.</span> The session token is used to search jobs and submit Easy Apply applications</li>
          </ol>
        </div>
      </div>
    </DashboardLayout>
  );
}
