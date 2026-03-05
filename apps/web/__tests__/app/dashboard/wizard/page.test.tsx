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

// Mock react-dropzone
jest.mock('react-dropzone', () => ({
  useDropzone: () => ({
    getRootProps: () => ({ onClick: jest.fn(), role: 'button', 'data-testid': 'dropzone' }),
    getInputProps: () => ({ 'data-testid': 'file-input' }),
    isDragActive: false,
    fileRejections: [],
  }),
}));

// Mock react-hot-toast
const mockToast = jest.fn();
const mockToastError = jest.fn();
jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: Object.assign(
    jest.fn((message: string) => mockToast(message)),
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
  });

  describe('Step 1: Resume Upload', () => {
    it('renders the wizard with step 1 active', () => {
      render(<WizardPage />);

      expect(screen.getByText('Create Job Search Profile')).toBeInTheDocument();
      expect(screen.getByText('Upload Your Resume')).toBeInTheDocument();
      expect(screen.getByText(/drag and drop your resume here/i)).toBeInTheDocument();
    });

    it('shows file type and size validation info', () => {
      render(<WizardPage />);

      expect(screen.getByText(/supports pdf, doc, docx \(max 5mb\)/i)).toBeInTheDocument();
    });

    it('disables next button when resume is not uploaded', () => {
      render(<WizardPage />);

      const nextButton = screen.getByRole('button', { name: /next/i });
      expect(nextButton).toBeDisabled();
    });

    it('disables previous button on step 1', () => {
      render(<WizardPage />);

      const prevButton = screen.getByRole('button', { name: /previous/i });
      expect(prevButton).toBeDisabled();
    });

    it('shows progress indicator with step labels', () => {
      render(<WizardPage />);

      expect(screen.getByText('Resume')).toBeInTheDocument();
      expect(screen.getByText('LinkedIn')).toBeInTheDocument();
      expect(screen.getByText('Profile')).toBeInTheDocument();
    });

    it('shows step numbers in progress indicator', () => {
      render(<WizardPage />);

      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  describe('Navigation', () => {
    it('renders Previous and Next buttons', () => {
      render(<WizardPage />);

      expect(screen.getByRole('button', { name: /previous/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    });
  });

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
  });

  describe('Step Content', () => {
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
