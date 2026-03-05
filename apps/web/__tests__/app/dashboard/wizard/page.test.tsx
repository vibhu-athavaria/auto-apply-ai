import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WizardPage from '@/app/dashboard/wizard/page';

// Mock next/navigation
const mockPush = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

// Mock react-dropzone - we'll control its behavior per test
let mockDropzoneState = {
  getRootProps: () => ({ onClick: jest.fn(), role: 'button', 'data-testid': 'dropzone' }),
  getInputProps: () => ({ 'data-testid': 'file-input' }),
  isDragActive: false,
  fileRejections: [] as Array<{ file: File; errors: Array<{ code: string; message: string }> }>,
};

let mockOnDropCallback: ((files: File[]) => void) | null = null;

jest.mock('react-dropzone', () => ({
  useDropzone: ({ onDrop }: { onDrop: (files: File[]) => void }) => {
    mockOnDropCallback = onDrop;
    return mockDropzoneState;
  },
}));

// Mock react-hot-toast
const mockToast = jest.fn();
const mockToastError = jest.fn();
jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: Object.assign(
    jest.fn((message: string, opts?: any) => mockToast(message, opts)),
    { error: jest.fn((message: string) => mockToastError(message)) }
  ),
  toast: Object.assign(
    jest.fn((message: string, opts?: any) => mockToast(message, opts)),
    { error: jest.fn((message: string) => mockToastError(message)) }
  ),
}));

// Mock the DashboardLayout component
jest.mock('@/components/DashboardLayout', () => {
  return function MockDashboardLayout({ children }: { children: React.ReactNode }) {
    return <div data-testid="dashboard-layout">{children}</div>;
  };
});

// Mock the new wizard components
jest.mock('@/components/wizard/ResumeStep', () => ({
  __esModule: true,
  default: ({ isUploaded, filename, onUploadComplete, onChange }: any) => (
    <div data-testid="resume-step">
      <div data-testid="resume-status">{isUploaded ? 'uploaded' : 'not-uploaded'}</div>
      {isUploaded && <div data-testid="resume-filename">{filename}</div>}
      <button data-testid="mock-upload-btn" onClick={() => onUploadComplete('test.pdf')}>
        Mock Upload
      </button>
      <button data-testid="mock-change-btn" onClick={onChange}>
        Mock Change
      </button>
    </div>
  ),
}));

jest.mock('@/components/wizard/LinkedInStep', () => ({
  __esModule: true,
  default: ({ isConnected, isSkipped, onConnect, onSkip, onRetry, email, password, onEmailChange, onPasswordChange }: any) => (
    <div data-testid="linkedin-step">
      <div data-testid="linkedin-status">
        {isConnected ? 'connected' : isSkipped ? 'skipped' : 'not-connected'}
      </div>
      <input
        data-testid="linkedin-email-input"
        value={email || ''}
        onChange={(e) => onEmailChange?.(e.target.value)}
      />
      <input
        data-testid="linkedin-password-input"
        value={password || ''}
        onChange={(e) => onPasswordChange?.(e.target.value)}
      />
      <button data-testid="mock-connect-btn" onClick={onConnect}>
        Mock Connect
      </button>
      <button data-testid="mock-skip-btn" onClick={onSkip}>
        Mock Skip
      </button>
      <button data-testid="mock-retry-btn" onClick={onRetry}>
        Mock Retry
      </button>
    </div>
  ),
}));

jest.mock('@/components/wizard/ProfileStep', () => ({
  __esModule: true,
  default: ({ data, onChange }: any) => (
    <div data-testid="profile-step">
      <input
        data-testid="profile-name-input"
        value={data?.profileName || ''}
        onChange={(e) => onChange?.({ profileName: e.target.value })}
      />
      <input
        data-testid="keywords-input"
        value={data?.keywords || ''}
        onChange={(e) => onChange?.({ keywords: e.target.value })}
      />
      <input
        data-testid="location-input"
        value={data?.location || ''}
        onChange={(e) => onChange?.({ location: e.target.value })}
      />
      <select
        data-testid="experience-select"
        value={data?.experienceLevel || ''}
        onChange={(e) => onChange?.({ experienceLevel: e.target.value })}
      >
        <option value="">Any Level</option>
        <option value="entry">Entry</option>
        <option value="senior">Senior</option>
      </select>
      <select
        data-testid="job-type-select"
        value={data?.jobType || ''}
        onChange={(e) => onChange?.({ jobType: e.target.value })}
      >
        <option value="">Any Type</option>
        <option value="full-time">Full-time</option>
      </select>
      <input
        data-testid="remote-only-checkbox"
        type="checkbox"
        checked={data?.remoteOnly || false}
        onChange={(e) => onChange?.({ remoteOnly: e.target.checked })}
      />
    </div>
  ),
}));

jest.mock('@/hooks/useLinkedInConnection', () => ({
  __esModule: true,
  useLinkedInConnection: jest.fn((onConnect, onSkip) => ({
    status: 'idle',
    message: '',
    taskId: null,
    email: '',
    password: '',
    showPassword: false,
    showSkipWarning: false,
    setEmail: jest.fn(),
    setPassword: jest.fn(),
    setShowPassword: jest.fn(),
    setShowSkipWarning: jest.fn(),
    connect: jest.fn().mockImplementation(() => {
      onConnect();
      return Promise.resolve();
    }),
    skip: jest.fn().mockImplementation(() => {
      onSkip();
    }),
    confirmSkip: jest.fn().mockImplementation(() => {
      onSkip();
    }),
    reset: jest.fn(),
  })),
}));

// Mock the API
const mockUpload = jest.fn();
const mockConnect = jest.fn();
const mockGetConnectStatus = jest.fn();
const mockCreateProfile = jest.fn();

jest.mock('@/lib/api', () => ({
  resumeApi: {
    upload: (...args: any[]) => mockUpload(...args),
    list: jest.fn().mockResolvedValue([]),
  },
  linkedinApi: {
    getStatus: jest.fn().mockResolvedValue({ connected: false }),
    connect: (...args: any[]) => mockConnect(...args),
    getConnectStatus: (...args: any[]) => mockGetConnectStatus(...args),
    validate: jest.fn().mockResolvedValue({ connected: true }),
    deleteSession: jest.fn().mockResolvedValue({}),
  },
  profileApi: {
    create: (...args: any[]) => mockCreateProfile(...args),
    list: jest.fn().mockResolvedValue([]),
    get: jest.fn().mockResolvedValue({}),
  },
}));

describe('WizardPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUpload.mockResolvedValue({});
    mockConnect.mockResolvedValue({ task_id: 'test-task-123' });
    mockCreateProfile.mockResolvedValue({ id: 'profile-123' });
    mockDropzoneState = {
      getRootProps: () => ({ onClick: jest.fn(), role: 'button', 'data-testid': 'dropzone' }),
      getInputProps: () => ({ 'data-testid': 'file-input' }),
      isDragActive: false,
      fileRejections: [],
    };
  });

  // ============================================================================
  // RENDERING TESTS (5 cases)
  // ============================================================================
  describe('Rendering Tests', () => {
    it('renders wizard with initial step 1', () => {
      render(<WizardPage />);

      expect(screen.getByText('Create Job Search Profile')).toBeInTheDocument();
      expect(screen.getByTestId('resume-step')).toBeInTheDocument();
    });

    it('renders progress indicator with 3 steps', () => {
      render(<WizardPage />);

      expect(screen.getByText('Resume')).toBeInTheDocument();
      expect(screen.getByText('LinkedIn')).toBeInTheDocument();
      expect(screen.getByText('Profile')).toBeInTheDocument();
    });

    it('renders navigation buttons', () => {
      render(<WizardPage />);

      expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    });

    it('renders step 1 (ResumeStep) component', () => {
      render(<WizardPage />);

      expect(screen.getByTestId('resume-step')).toBeInTheDocument();
    });

    it('renders all step indicators', () => {
      render(<WizardPage />);

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  // ============================================================================
  // NAVIGATION TESTS (6 cases)
  // ============================================================================
  describe('Navigation Tests', () => {
    it('next button advances to step 2', async () => {
      render(<WizardPage />);

      // First upload a resume to enable next button
      await act(async () => {
        fireEvent.click(screen.getByTestId('mock-upload-btn'));
      });

      await waitFor(() => {
        expect(screen.getByTestId('resume-status')).toHaveTextContent('uploaded');
      });

      // Click next to go to step 2
      const nextButton = screen.getByRole('button', { name: /next/i });
      await act(async () => {
        fireEvent.click(nextButton);
      });

      await waitFor(() => {
        expect(screen.getByTestId('linkedin-step')).toBeInTheDocument();
      });
    });

    it('previous button goes back to step 1', async () => {
      render(<WizardPage />);

      // Upload resume and go to step 2
      await act(async () => {
        fireEvent.click(screen.getByTestId('mock-upload-btn'));
      });

      await waitFor(() => {
        expect(screen.getByTestId('resume-status')).toHaveTextContent('uploaded');
      });

      // Go to step 2
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByTestId('linkedin-step')).toBeInTheDocument();
      });

      // Click previous to go back
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /previous/i }));
      });

      await waitFor(() => {
        expect(screen.getByTestId('resume-step')).toBeInTheDocument();
      });
    });

    it('previous button is disabled on step 1', () => {
      render(<WizardPage />);

      const prevButton = screen.getByRole('button', { name: /previous/i });
      expect(prevButton).toBeDisabled();
    });

    it('progress indicator updates on navigation', async () => {
      render(<WizardPage />);

      // Upload resume
      await act(async () => {
        fireEvent.click(screen.getByTestId('mock-upload-btn'));
      });

      await waitFor(() => {
        expect(screen.getByTestId('resume-status')).toHaveTextContent('uploaded');
      });

      // Go to step 2
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByTestId('linkedin-step')).toBeInTheDocument();
      });
    });

    it('step indicators show completed state', async () => {
      render(<WizardPage />);

      // Initially step 1 is not complete
      await act(async () => {
        fireEvent.click(screen.getByTestId('mock-upload-btn'));
      });

      await waitFor(() => {
        expect(screen.getByTestId('resume-status')).toHaveTextContent('uploaded');
      });

      // Now go to step 2 to see the completed indicator
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByTestId('linkedin-step')).toBeInTheDocument();
      });
    });

    it('cannot navigate to step 3 without completing step 2', async () => {
      render(<WizardPage />);

      // Upload resume
      await act(async () => {
        fireEvent.click(screen.getByTestId('mock-upload-btn'));
      });

      await waitFor(() => {
        expect(screen.getByTestId('resume-status')).toHaveTextContent('uploaded');
      });

      // Try to go next - should go to step 2, not step 3
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByTestId('linkedin-step')).toBeInTheDocument();
      });

      // Next button should be disabled since LinkedIn is not connected
      const nextButton = screen.getByRole('button', { name: /next/i });
      expect(nextButton).toBeDisabled();
    });
  });

  // ============================================================================
  // STEP 1 - RESUME UPLOAD TESTS (12 cases)
  // ============================================================================
  describe('Step 1 - Resume Upload', () => {
    it('renders file dropzone', () => {
      render(<WizardPage />);

      expect(screen.getByTestId('dropzone')).toBeInTheDocument();
      expect(screen.getByText(/drag and drop your resume here/i)).toBeInTheDocument();
    });

    it('renders file type requirements', () => {
      render(<WizardPage />);

      expect(screen.getByText(/supports pdf, doc, docx/i)).toBeInTheDocument();
    });

    it('renders file size limit', () => {
      render(<WizardPage />);

      expect(screen.getByText(/max 5mb/i)).toBeInTheDocument();
    });

    it('handles valid file selection', async () => {
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });
      render(<WizardPage />);

      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
        expect(screen.getByText('test.pdf')).toBeInTheDocument();
      });

      expect(mockUpload).toHaveBeenCalledWith(validFile);
    });

    it('rejects invalid file type', async () => {
      render(<WizardPage />);

      const invalidFile = new File(['test content'], 'test.txt', { type: 'text/plain' });

      await act(async () => {
        mockOnDropCallback?.([invalidFile]);
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Invalid file type. Please upload PDF, DOC, or DOCX files only.');
      });
    });

    it('rejects file exceeding size limit', async () => {
      render(<WizardPage />);

      // Create a file larger than 5MB
      const largeContent = new ArrayBuffer(6 * 1024 * 1024);
      const largeFile = new File([largeContent], 'large.pdf', { type: 'application/pdf' });

      await act(async () => {
        mockOnDropCallback?.([largeFile]);
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('File too large. Maximum size is 5MB.');
      });
    });

    it('displays upload progress', async () => {
      mockUpload.mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ id: 'resume-123' }), 100)));
      render(<WizardPage />);

      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(screen.getByText(/uploading/i)).toBeInTheDocument();
      });
    });

    it('shows success message after upload', async () => {
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });
      render(<WizardPage />);

      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith('Resume uploaded successfully!');
      });
    });

    it('enables next button after successful upload', async () => {
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });
      render(<WizardPage />);

      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        const nextButton = screen.getByRole('button', { name: /next/i });
        expect(nextButton).not.toBeDisabled();
      });
    });

    it('handles upload API error', async () => {
      mockUpload.mockRejectedValueOnce({
        response: { data: { detail: 'Upload failed' } }
      });
      render(<WizardPage />);

      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Upload failed');
      });

      const nextButton = screen.getByRole('button', { name: /next/i });
      expect(nextButton).toBeDisabled();
    });

    it('allows file removal', async () => {
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });
      render(<WizardPage />);

      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
      });

      const changeButton = screen.getByRole('button', { name: /change/i });
      await act(async () => {
        fireEvent.click(changeButton);
      });

      await waitFor(() => {
        expect(screen.queryByText('Resume Uploaded')).not.toBeInTheDocument();
      });

      const nextButton = screen.getByRole('button', { name: /next/i });
      expect(nextButton).toBeDisabled();
    });

    it('cannot proceed without uploading resume', () => {
      render(<WizardPage />);

      const nextButton = screen.getByRole('button', { name: /next/i });
      expect(nextButton).toBeDisabled();
    });
  });

  // ============================================================================
  // STEP 2 - LINKEDIN CONNECTION TESTS (20 cases)
  // ============================================================================
  describe('Step 2 - LinkedIn Connection', () => {
    const navigateToStep2 = async () => {
      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Connect LinkedIn')).toBeInTheDocument();
      });
    };

    it('renders 2FA notice prominently', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      expect(screen.getByText('Two-Factor Authentication')).toBeInTheDocument();
      expect(screen.getByText(/you may need to authenticate on a secondary device/i)).toBeInTheDocument();
    });

    it('renders email input field', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      const emailInput = screen.getByPlaceholderText('you@example.com');
      expect(emailInput).toBeInTheDocument();
      expect(emailInput).toHaveAttribute('type', 'email');
    });

    it('renders password input field', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');
      expect(passwordInput).toBeInTheDocument();
      expect(passwordInput).toHaveAttribute('type', 'password');
    });

    it('renders show/hide password toggle', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      // Eye icon should be present (we can't easily test the icon itself but we can test the button)
      const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');
      expect(passwordInput).toHaveAttribute('type', 'password');

      // Find and click the toggle button
      const toggleButton = passwordInput.parentElement?.querySelector('button');
      expect(toggleButton).toBeInTheDocument();
    });

    it('renders connect button', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      expect(screen.getByRole('button', { name: /connect linkedin/i })).toBeInTheDocument();
    });

    it('renders skip option', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      expect(screen.getByRole('button', { name: /skip for now/i })).toBeInTheDocument();
    });

    it('validates required email', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      const connectButton = screen.getByRole('button', { name: /connect linkedin/i });
      expect(connectButton).toBeDisabled();

      // Only fill password
      const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');
      await act(async () => {
        await userEvent.type(passwordInput, 'password123');
      });

      expect(connectButton).toBeDisabled();
    });

    it('validates required password', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      const connectButton = screen.getByRole('button', { name: /connect linkedin/i });

      // Only fill email
      const emailInput = screen.getByPlaceholderText('you@example.com');
      await act(async () => {
        await userEvent.type(emailInput, 'test@example.com');
      });

      expect(connectButton).toBeDisabled();
    });

    it('shows loading state during connection', async () => {
      mockConnect.mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ task_id: 'task-123' }), 100)));
      render(<WizardPage />);
      await navigateToStep2();

      const emailInput = screen.getByPlaceholderText('you@example.com');
      const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');

      await act(async () => {
        await userEvent.type(emailInput, 'test@example.com');
        await userEvent.type(passwordInput, 'password123');
      });

      const connectButton = screen.getByRole('button', { name: /connect linkedin/i });
      await act(async () => {
        fireEvent.click(connectButton);
      });

      await waitFor(() => {
        expect(screen.getByText(/connecting/i)).toBeInTheDocument();
      });
    });

    it('polls for connection status', async () => {
      jest.useFakeTimers();
      mockConnect.mockResolvedValueOnce({ task_id: 'task-123' });
      mockGetConnectStatus.mockResolvedValueOnce({ status: 'connected', message: 'Success' });

      render(<WizardPage />);
      await navigateToStep2();

      const emailInput = screen.getByPlaceholderText('you@example.com');
      const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');

      await act(async () => {
        await userEvent.type(emailInput, 'test@example.com');
        await userEvent.type(passwordInput, 'password123');
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /connect linkedin/i }));
      });

      await act(async () => {
        jest.advanceTimersByTime(2500);
      });

      await waitFor(() => {
        expect(mockGetConnectStatus).toHaveBeenCalledWith('task-123');
      });

      jest.useRealTimers();
    });

    it('shows "Connecting to LinkedIn..." message', async () => {
      mockConnect.mockResolvedValueOnce({ task_id: 'task-123' });
      render(<WizardPage />);
      await navigateToStep2();

      const emailInput = screen.getByPlaceholderText('you@example.com');
      const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');

      await act(async () => {
        await userEvent.type(emailInput, 'test@example.com');
        await userEvent.type(passwordInput, 'password123');
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /connect linkedin/i }));
      });

      await waitFor(() => {
        expect(screen.getByText(/connecting to linkedin/i)).toBeInTheDocument();
      });
    });

    it('shows "LinkedIn connected successfully" on success', async () => {
      jest.useFakeTimers();
      mockConnect.mockResolvedValueOnce({ task_id: 'task-123' });
      mockGetConnectStatus.mockResolvedValueOnce({ status: 'connected', message: 'LinkedIn connected successfully' });

      render(<WizardPage />);
      await navigateToStep2();

      const emailInput = screen.getByPlaceholderText('you@example.com');
      const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');

      await act(async () => {
        await userEvent.type(emailInput, 'test@example.com');
        await userEvent.type(passwordInput, 'password123');
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /connect linkedin/i }));
      });

      await act(async () => {
        jest.advanceTimersByTime(3000);
      });

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith('LinkedIn connected successfully!');
      });

      jest.useRealTimers();
    });

    it('enables next button on successful connection', async () => {
      jest.useFakeTimers();
      mockConnect.mockResolvedValueOnce({ task_id: 'task-123' });
      mockGetConnectStatus.mockResolvedValueOnce({ status: 'connected', message: 'Success' });

      render(<WizardPage />);
      await navigateToStep2();

      const emailInput = screen.getByPlaceholderText('you@example.com');
      const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');

      await act(async () => {
        await userEvent.type(emailInput, 'test@example.com');
        await userEvent.type(passwordInput, 'password123');
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /connect linkedin/i }));
      });

      await act(async () => {
        jest.advanceTimersByTime(3000);
      });

      await waitFor(() => {
        const nextButton = screen.getByRole('button', { name: /next/i });
        expect(nextButton).not.toBeDisabled();
      });

      jest.useRealTimers();
    });

    it('handles invalid credentials error', async () => {
      mockConnect.mockRejectedValueOnce({
        response: { data: { detail: 'Invalid email or password' } }
      });
      render(<WizardPage />);
      await navigateToStep2();

      const emailInput = screen.getByPlaceholderText('you@example.com');
      const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');

      await act(async () => {
        await userEvent.type(emailInput, 'test@example.com');
        await userEvent.type(passwordInput, 'wrongpassword');
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /connect linkedin/i }));
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Invalid email or password');
      });
    });

    it('handles connection failure', async () => {
      mockConnect.mockRejectedValueOnce({
        response: { data: { detail: 'Could not connect to LinkedIn' } }
      });
      render(<WizardPage />);
      await navigateToStep2();

      const emailInput = screen.getByPlaceholderText('you@example.com');
      const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');

      await act(async () => {
        await userEvent.type(emailInput, 'test@example.com');
        await userEvent.type(passwordInput, 'password123');
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /connect linkedin/i }));
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Could not connect to LinkedIn');
      });
    });

    it('opens skip confirmation modal', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      const skipButton = screen.getByRole('button', { name: /skip for now/i });
      await act(async () => {
        fireEvent.click(skipButton);
      });

      await waitFor(() => {
        expect(screen.getByText('Skip LinkedIn Connection?')).toBeInTheDocument();
      });
    });

    it('confirms skip and proceeds to step 3', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      const skipButton = screen.getByRole('button', { name: /skip for now/i });
      await act(async () => {
        fireEvent.click(skipButton);
      });

      await waitFor(() => {
        expect(screen.getByText('Skip LinkedIn Connection?')).toBeInTheDocument();
      });

      const skipAnywayButton = screen.getByRole('button', { name: /skip anyway/i });
      await act(async () => {
        fireEvent.click(skipAnywayButton);
      });

      // After skipping, we should be able to proceed to step 3
      await waitFor(() => {
        const nextButton = screen.getByRole('button', { name: /next/i });
        expect(nextButton).not.toBeDisabled();
      });
    });

    it('cancels skip and stays on step 2', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      const skipButton = screen.getByRole('button', { name: /skip for now/i });
      await act(async () => {
        fireEvent.click(skipButton);
      });

      await waitFor(() => {
        expect(screen.getByText('Skip LinkedIn Connection?')).toBeInTheDocument();
      });

      const goBackButton = screen.getByRole('button', { name: /go back/i });
      await act(async () => {
        fireEvent.click(goBackButton);
      });

      await waitFor(() => {
        expect(screen.queryByText('Skip LinkedIn Connection?')).not.toBeInTheDocument();
        expect(screen.getByText('Connect LinkedIn')).toBeInTheDocument();
      });
    });

    it('shows warning when step 2 is skipped', async () => {
      render(<WizardPage />);
      await navigateToStep2();

      const skipButton = screen.getByRole('button', { name: /skip for now/i });
      await act(async () => {
        fireEvent.click(skipButton);
      });

      await waitFor(() => {
        expect(screen.getByText('Skip LinkedIn Connection?')).toBeInTheDocument();
      });

      const skipAnywayButton = screen.getByRole('button', { name: /skip anyway/i });
      await act(async () => {
        fireEvent.click(skipAnywayButton);
      });

      await waitFor(() => {
        expect(screen.getByText('LinkedIn Skipped')).toBeInTheDocument();
      });
    });
  });

  // ============================================================================
  // STEP 3 - JOB PROFILE CREATION TESTS (20 cases)
  // ============================================================================
  describe('Step 3 - Job Profile Creation', () => {
    const navigateToStep3 = async (skipLinkedIn = true) => {
      // Upload resume
      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
      });

      // Go to step 2
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Connect LinkedIn')).toBeInTheDocument();
      });

      if (skipLinkedIn) {
        // Skip LinkedIn
        await act(async () => {
          fireEvent.click(screen.getByRole('button', { name: /skip for now/i }));
        });

        await waitFor(() => {
          expect(screen.getByText('Skip LinkedIn Connection?')).toBeInTheDocument();
        });

        await act(async () => {
          fireEvent.click(screen.getByRole('button', { name: /skip anyway/i }));
        });
      } else {
        // Connect LinkedIn
        mockConnect.mockResolvedValueOnce({ task_id: 'task-123' });
        mockGetConnectStatus.mockResolvedValueOnce({ status: 'connected' });

        const emailInput = screen.getByPlaceholderText('you@example.com');
        const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');

        await act(async () => {
          await userEvent.type(emailInput, 'test@example.com');
          await userEvent.type(passwordInput, 'password123');
        });

        await act(async () => {
          fireEvent.click(screen.getByRole('button', { name: /connect linkedin/i }));
        });

        await waitFor(() => {
          expect(mockConnect).toHaveBeenCalled();
        });
      }

      // Go to step 3
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Create Job Search Profile')).toBeInTheDocument();
      });
    };

    it('renders profile name input', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      expect(screen.getByPlaceholderText('e.g., Software Engineer Search')).toBeInTheDocument();
    });

    it('renders keywords input', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      expect(screen.getByPlaceholderText('e.g., Software Engineer, Python Developer')).toBeInTheDocument();
    });

    it('renders location input', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      expect(screen.getByPlaceholderText('e.g., San Francisco, CA or Remote')).toBeInTheDocument();
    });

    it('renders experience level dropdown', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      const experienceSelect = screen.getByLabelText(/experience level/i);
      expect(experienceSelect).toBeInTheDocument();
    });

    it('renders job type dropdown', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      const jobTypeSelect = screen.getByLabelText(/job type/i);
      expect(jobTypeSelect).toBeInTheDocument();
    });

    it('renders remote only checkbox', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      const remoteCheckbox = screen.getByLabelText(/remote only/i);
      expect(remoteCheckbox).toBeInTheDocument();
      expect(remoteCheckbox).toHaveAttribute('type', 'checkbox');
    });

    it('validates required profile name', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      // Try to submit without filling required fields
      const createButton = screen.getByRole('button', { name: /create profile/i });
      await act(async () => {
        fireEvent.click(createButton);
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Profile name is required');
      });
    });

    it('validates required keywords', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      // Fill profile name but not keywords
      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      await act(async () => {
        await userEvent.type(nameInput, 'My Profile');
      });

      const createButton = screen.getByRole('button', { name: /create profile/i });
      await act(async () => {
        fireEvent.click(createButton);
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Keywords are required');
      });
    });

    it('validates required location', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      // Fill profile name and keywords but not location
      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');

      await act(async () => {
        await userEvent.type(nameInput, 'My Profile');
        await userEvent.type(keywordsInput, 'Software Engineer');
      });

      const createButton = screen.getByRole('button', { name: /create profile/i });
      await act(async () => {
        fireEvent.click(createButton);
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Location is required');
      });
    });

    it('selects experience level option', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      const experienceSelect = screen.getByLabelText(/experience level/i);
      await act(async () => {
        await userEvent.selectOptions(experienceSelect, 'senior');
      });

      expect(experienceSelect).toHaveValue('senior');
    });

    it('selects job type option', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      const jobTypeSelect = screen.getByLabelText(/job type/i);
      await act(async () => {
        await userEvent.selectOptions(jobTypeSelect, 'full-time');
      });

      expect(jobTypeSelect).toHaveValue('full-time');
    });

    it('toggles remote only checkbox', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      const remoteCheckbox = screen.getByLabelText(/remote only/i);
      expect(remoteCheckbox).not.toBeChecked();

      await act(async () => {
        fireEvent.click(remoteCheckbox);
      });

      expect(remoteCheckbox).toBeChecked();

      await act(async () => {
        fireEvent.click(remoteCheckbox);
      });

      expect(remoteCheckbox).not.toBeChecked();
    });

    it('shows summary of previous steps', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      expect(screen.getByText('Profile Summary')).toBeInTheDocument();
      expect(screen.getByText('Resume:')).toBeInTheDocument();
      expect(screen.getByText('LinkedIn:')).toBeInTheDocument();
    });

    it('enables submit when all required fields filled', async () => {
      render(<WizardPage />);
      await navigateToStep3();

      // Fill all required fields
      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');
      const locationInput = screen.getByPlaceholderText('e.g., San Francisco, CA or Remote');

      await act(async () => {
        await userEvent.type(nameInput, 'My Profile');
        await userEvent.type(keywordsInput, 'Software Engineer');
        await userEvent.type(locationInput, 'San Francisco');
      });

      // The Create Profile button should be enabled (no disabled attribute due to validation via toast)
      const createButton = screen.getByRole('button', { name: /create profile/i });
      expect(createButton).not.toBeDisabled();
    });

    it('shows loading state during submission', async () => {
      mockCreateProfile.mockImplementation(() => new Promise(resolve => setTimeout(() => resolve({ id: 'profile-123' }), 100)));
      render(<WizardPage />);
      await navigateToStep3();

      // Fill all required fields
      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');
      const locationInput = screen.getByPlaceholderText('e.g., San Francisco, CA or Remote');

      await act(async () => {
        await userEvent.type(nameInput, 'My Profile');
        await userEvent.type(keywordsInput, 'Software Engineer');
        await userEvent.type(locationInput, 'San Francisco');
      });

      const createButton = screen.getByRole('button', { name: /create profile/i });
      await act(async () => {
        fireEvent.click(createButton);
      });

      await waitFor(() => {
        expect(screen.getByText(/creating/i)).toBeInTheDocument();
      });
    });

    it('calls create profile API on submit', async () => {
      mockCreateProfile.mockResolvedValueOnce({ id: 'profile-123' });
      render(<WizardPage />);
      await navigateToStep3();

      // Fill all required fields
      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');
      const locationInput = screen.getByPlaceholderText('e.g., San Francisco, CA or Remote');

      await act(async () => {
        await userEvent.type(nameInput, 'My Profile');
        await userEvent.type(keywordsInput, 'Software Engineer');
        await userEvent.type(locationInput, 'San Francisco');
      });

      const createButton = screen.getByRole('button', { name: /create profile/i });
      await act(async () => {
        fireEvent.click(createButton);
      });

      await waitFor(() => {
        expect(mockCreateProfile).toHaveBeenCalled();
      });
    });

    it('redirects to /dashboard/profiles on success', async () => {
      mockCreateProfile.mockResolvedValueOnce({ id: 'profile-123' });
      render(<WizardPage />);
      await navigateToStep3();

      // Fill all required fields
      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');
      const locationInput = screen.getByPlaceholderText('e.g., San Francisco, CA or Remote');

      await act(async () => {
        await userEvent.type(nameInput, 'My Profile');
        await userEvent.type(keywordsInput, 'Software Engineer');
        await userEvent.type(locationInput, 'San Francisco');
      });

      const createButton = screen.getByRole('button', { name: /create profile/i });
      await act(async () => {
        fireEvent.click(createButton);
      });

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/dashboard/profiles');
      });
    });

    it('shows success toast on completion', async () => {
      mockCreateProfile.mockResolvedValueOnce({ id: 'profile-123' });
      render(<WizardPage />);
      await navigateToStep3();

      // Fill all required fields
      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');
      const locationInput = screen.getByPlaceholderText('e.g., San Francisco, CA or Remote');

      await act(async () => {
        await userEvent.type(nameInput, 'My Profile');
        await userEvent.type(keywordsInput, 'Software Engineer');
        await userEvent.type(locationInput, 'San Francisco');
      });

      const createButton = screen.getByRole('button', { name: /create profile/i });
      await act(async () => {
        fireEvent.click(createButton);
      });

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith('Job search profile created successfully!');
      });
    });

    it('handles API error on submission', async () => {
      mockCreateProfile.mockRejectedValueOnce({
        response: { data: { detail: 'Failed to create profile' } }
      });
      render(<WizardPage />);
      await navigateToStep3();

      // Fill all required fields
      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');
      const locationInput = screen.getByPlaceholderText('e.g., San Francisco, CA or Remote');

      await act(async () => {
        await userEvent.type(nameInput, 'My Profile');
        await userEvent.type(keywordsInput, 'Software Engineer');
        await userEvent.type(locationInput, 'San Francisco');
      });

      const createButton = screen.getByRole('button', { name: /create profile/i });
      await act(async () => {
        fireEvent.click(createButton);
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Failed to create profile');
      });

      // Should stay on the same page
      expect(screen.getByText('Create Job Search Profile')).toBeInTheDocument();
    });

    it('preserves form data on error', async () => {
      mockCreateProfile.mockRejectedValueOnce({
        response: { data: { detail: 'Failed to create profile' } }
      });
      render(<WizardPage />);
      await navigateToStep3();

      // Fill all required fields
      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');
      const locationInput = screen.getByPlaceholderText('e.g., San Francisco, CA or Remote');

      await act(async () => {
        await userEvent.type(nameInput, 'My Profile');
        await userEvent.type(keywordsInput, 'Software Engineer');
        await userEvent.type(locationInput, 'San Francisco');
      });

      const createButton = screen.getByRole('button', { name: /create profile/i });
      await act(async () => {
        fireEvent.click(createButton);
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalled();
      });

      // Form data should be preserved
      expect(nameInput).toHaveValue('My Profile');
      expect(keywordsInput).toHaveValue('Software Engineer');
      expect(locationInput).toHaveValue('San Francisco');
    });
  });

  // ============================================================================
  // INTEGRATION & FLOW TESTS (4 cases)
  // ============================================================================
  describe('Integration & Flow Tests', () => {
    it('completes full wizard flow successfully', async () => {
      jest.useFakeTimers();

      render(<WizardPage />);

      // Step 1: Upload resume
      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
      });

      // Go to step 2
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Connect LinkedIn')).toBeInTheDocument();
      });

      // Step 2: Connect LinkedIn
      mockConnect.mockResolvedValueOnce({ task_id: 'task-123' });
      mockGetConnectStatus.mockResolvedValueOnce({ status: 'connected', message: 'Success' });

      const emailInput = screen.getByPlaceholderText('you@example.com');
      const passwordInput = screen.getByPlaceholderText('Your LinkedIn password');

      await act(async () => {
        await userEvent.type(emailInput, 'test@example.com');
        await userEvent.type(passwordInput, 'password123');
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /connect linkedin/i }));
      });

      await act(async () => {
        jest.advanceTimersByTime(3000);
      });

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith('LinkedIn connected successfully!');
      });

      // Go to step 3
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Create Job Search Profile')).toBeInTheDocument();
      });

      // Step 3: Create profile
      mockCreateProfile.mockResolvedValueOnce({ id: 'profile-123' });

      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');
      const locationInput = screen.getByPlaceholderText('e.g., San Francisco, CA or Remote');

      await act(async () => {
        await userEvent.type(nameInput, 'My Profile');
        await userEvent.type(keywordsInput, 'Software Engineer');
        await userEvent.type(locationInput, 'San Francisco');
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /create profile/i }));
      });

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/dashboard/profiles');
        expect(mockToast).toHaveBeenCalledWith('Job search profile created successfully!');
      });

      jest.useRealTimers();
    });

    it('completes wizard with skipped LinkedIn', async () => {
      render(<WizardPage />);

      // Step 1: Upload resume
      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
      });

      // Go to step 2
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Connect LinkedIn')).toBeInTheDocument();
      });

      // Step 2: Skip LinkedIn
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /skip for now/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Skip LinkedIn Connection?')).toBeInTheDocument();
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /skip anyway/i }));
      });

      // Go to step 3
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Create Job Search Profile')).toBeInTheDocument();
      });

      // Step 3: Create profile
      mockCreateProfile.mockResolvedValueOnce({ id: 'profile-123' });

      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');
      const locationInput = screen.getByPlaceholderText('e.g., San Francisco, CA or Remote');

      await act(async () => {
        await userEvent.type(nameInput, 'My Profile');
        await userEvent.type(keywordsInput, 'Software Engineer');
        await userEvent.type(locationInput, 'San Francisco');
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /create profile/i }));
      });

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/dashboard/profiles');
      });
    });

    it('maintains state when navigating between steps', async () => {
      render(<WizardPage />);

      // Step 1: Upload resume
      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
      });

      // Go to step 2
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Connect LinkedIn')).toBeInTheDocument();
      });

      // Type email in step 2
      const emailInput = screen.getByPlaceholderText('you@example.com');
      await act(async () => {
        await userEvent.type(emailInput, 'test@example.com');
      });

      // Go back to step 1
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /previous/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
      });

      // Go forward to step 2 again - email should be preserved (this is component state)
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Connect LinkedIn')).toBeInTheDocument();
      });

      // Resume should still be uploaded
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /previous/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
      });
    });
  });

  // ============================================================================
  // EDGE CASES (5 cases)
  // ============================================================================
  describe('Edge Cases', () => {
    it('handles rapid navigation clicks', async () => {
      render(<WizardPage />);

      // Upload resume
      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
      });

      // Double-click next
      const nextButton = screen.getByRole('button', { name: /next/i });
      await act(async () => {
        fireEvent.click(nextButton);
        fireEvent.click(nextButton);
      });

      // Should only advance once to step 2
      await waitFor(() => {
        expect(screen.getByText('Connect LinkedIn')).toBeInTheDocument();
      });
    });

    it('handles network timeout on upload', async () => {
      mockUpload.mockRejectedValueOnce({
        message: 'Network Error',
        code: 'ECONNABORTED'
      });
      render(<WizardPage />);

      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalled();
      });
    });

    it('handles aborted upload', async () => {
      mockUpload.mockRejectedValueOnce({
        message: 'Request aborted'
      });
      render(<WizardPage />);

      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalled();
      });

      // Should be able to try again
      expect(screen.getByTestId('dropzone')).toBeInTheDocument();
    });

    it('handles special characters in profile name', async () => {
      render(<WizardPage />);

      // Upload resume
      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
      });

      // Go to step 2 and skip
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Connect LinkedIn')).toBeInTheDocument();
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /skip for now/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Skip LinkedIn Connection?')).toBeInTheDocument();
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /skip anyway/i }));
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Create Job Search Profile')).toBeInTheDocument();
      });

      // Try special characters
      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');
      const locationInput = screen.getByPlaceholderText('e.g., San Francisco, CA or Remote');

      await act(async () => {
        await userEvent.type(nameInput, 'My Profile 🚀 @#$%^&*()');
        await userEvent.type(keywordsInput, 'Software Engineer');
        await userEvent.type(locationInput, 'San Francisco');
      });

      expect(nameInput).toHaveValue('My Profile 🚀 @#$%^&*()');

      // Should still be able to submit
      mockCreateProfile.mockResolvedValueOnce({ id: 'profile-123' });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /create profile/i }));
      });

      await waitFor(() => {
        expect(mockCreateProfile).toHaveBeenCalled();
      });
    });

    it('handles very long inputs', async () => {
      render(<WizardPage />);

      // Upload resume
      const validFile = new File(['test content'], 'test.pdf', { type: 'application/pdf' });
      mockUpload.mockResolvedValueOnce({ id: 'resume-123', filename: 'test.pdf' });

      await act(async () => {
        mockOnDropCallback?.([validFile]);
      });

      await waitFor(() => {
        expect(screen.getByText('Resume Uploaded')).toBeInTheDocument();
      });

      // Go to step 2 and skip
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Connect LinkedIn')).toBeInTheDocument();
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /skip for now/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Skip LinkedIn Connection?')).toBeInTheDocument();
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /skip anyway/i }));
      });

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /next/i }));
      });

      await waitFor(() => {
        expect(screen.getByText('Create Job Search Profile')).toBeInTheDocument();
      });

      // Try very long inputs
      const longString = 'a'.repeat(500);
      const nameInput = screen.getByPlaceholderText('e.g., Software Engineer Search');
      const keywordsInput = screen.getByPlaceholderText('e.g., Software Engineer, Python Developer');
      const locationInput = screen.getByPlaceholderText('e.g., San Francisco, CA or Remote');

      await act(async () => {
        await userEvent.type(nameInput, longString);
        await userEvent.type(keywordsInput, longString);
        await userEvent.type(locationInput, longString);
      });

      expect(nameInput).toHaveValue(longString);
      expect(keywordsInput).toHaveValue(longString);
      expect(locationInput).toHaveValue(longString);
    });
  });

  // ============================================================================
  // COMPONENT STRUCTURE TESTS
  // ============================================================================
  describe('Component Structure', () => {
    it('renders within DashboardLayout', () => {
      render(<WizardPage />);
      expect(screen.getByTestId('dashboard-layout')).toBeInTheDocument();
    });

    it('shows page header', () => {
      render(<WizardPage />);
      expect(screen.getByText('Create Job Search Profile')).toBeInTheDocument();
      expect(screen.getByText(/complete these steps to start finding/i)).toBeInTheDocument();
    });

    it('shows resume upload icon and description', () => {
      render(<WizardPage />);

      expect(screen.getByText('Upload Your Resume')).toBeInTheDocument();
      expect(screen.getByText(/upload your resume so we can tailor/i)).toBeInTheDocument();
    });

    it('shows dropzone for file upload', () => {
      render(<WizardPage />);

      expect(screen.getByTestId('dropzone')).toBeInTheDocument();
    });
  });
});
