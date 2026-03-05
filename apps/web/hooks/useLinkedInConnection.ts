'use client';

import { useState, useEffect, useCallback } from 'react';
import { linkedinApi } from '@/lib/api';
import toast from 'react-hot-toast';

type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'failed' | 'skipped';

interface UseLinkedInConnectionReturn {
  status: ConnectionStatus;
  message: string;
  taskId: string | null;
  email: string;
  password: string;
  showPassword: boolean;
  showSkipWarning: boolean;
  setEmail: (email: string) => void;
  setPassword: (password: string) => void;
  setShowPassword: (show: boolean) => void;
  setShowSkipWarning: (show: boolean) => void;
  connect: (email: string, password: string) => Promise<void>;
  skip: () => void;
  confirmSkip: () => void;
  reset: () => void;
}

export function useLinkedInConnection(
  onConnect: () => void,
  onSkip: () => void
): UseLinkedInConnectionReturn {
  const [status, setStatus] = useState<ConnectionStatus>('idle');
  const [message, setMessage] = useState('');
  const [taskId, setTaskId] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showSkipWarning, setShowSkipWarning] = useState(false);

  // Poll for connection status
  useEffect(() => {
    if (!taskId) return;

    const interval = setInterval(async () => {
      try {
        const taskStatus = await linkedinApi.getConnectStatus(taskId);

        if (taskStatus.status === 'connected') {
          clearInterval(interval);
          setTaskId(null);
          setStatus('connected');
          setMessage('LinkedIn connected successfully!');
          onConnect();
          toast.success('LinkedIn connected successfully!');
        } else if (taskStatus.status === 'failed') {
          clearInterval(interval);
          setTaskId(null);
          setStatus('failed');
          setMessage(taskStatus.message || 'Connection failed');
          toast.error(taskStatus.message || 'Connection failed');
        } else if (taskStatus.status === 'challenge_required') {
          clearInterval(interval);
          setTaskId(null);
          setStatus('failed');
          setMessage('LinkedIn requires verification. Please check your email or phone.');
          toast.error('LinkedIn requires verification');
        } else {
          setMessage('Connecting to LinkedIn...');
        }
      } catch {
        clearInterval(interval);
        setTaskId(null);
        setStatus('failed');
        setMessage('Failed to check connection status');
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [taskId, onConnect]);

  const connect = useCallback(async (email: string, password: string) => {
    if (!email.trim() || !password.trim()) {
      toast.error('Please enter your LinkedIn email and password');
      return;
    }

    setStatus('connecting');
    setMessage('Starting connection...');

    try {
      const result = await linkedinApi.connect(email, password);
      setTaskId(result.task_id);
      setMessage('Connecting to LinkedIn...');
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || 'Failed to start connection';
      setStatus('failed');
      setMessage(errorMessage);
      toast.error(errorMessage);
    }
  }, []);

  const skip = useCallback(() => {
    setShowSkipWarning(true);
  }, []);

  const confirmSkip = useCallback(() => {
    setStatus('skipped');
    setShowSkipWarning(false);
    onSkip();
    toast('LinkedIn connection skipped. You can connect later.', { icon: '⚠️' });
  }, [onSkip]);

  const reset = useCallback(() => {
    setStatus('idle');
    setMessage('');
    setTaskId(null);
    setShowSkipWarning(false);
  }, []);

  return {
    status,
    message,
    taskId,
    email,
    password,
    showPassword,
    showSkipWarning,
    setEmail,
    setPassword,
    setShowPassword,
    setShowSkipWarning,
    connect,
    skip,
    confirmSkip,
    reset,
  };
}
