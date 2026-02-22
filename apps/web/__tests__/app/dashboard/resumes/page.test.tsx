import { render, screen } from '@testing-library/react';
import ResumesPage from '@/app/dashboard/resumes/page';

// Mock react-dropzone
jest.mock('react-dropzone', () => ({
  useDropzone: () => ({
    getRootProps: () => ({ onClick: jest.fn() }),
    getInputProps: () => ({}),
    isDragActive: false,
  }),
}));

// Mock the DashboardLayout component
jest.mock('@/components/DashboardLayout', () => {
  return function MockDashboardLayout({ children }: { children: React.ReactNode }) {
    return <div data-testid="dashboard-layout">{children}</div>;
  };
});

// Mock the API
jest.mock('@/lib/api', () => ({
  resumeApi: {
    list: jest.fn().mockResolvedValue([]),
    upload: jest.fn().mockResolvedValue({}),
    delete: jest.fn().mockResolvedValue({}),
    download: jest.fn().mockResolvedValue(new Blob()),
  },
}));

describe('ResumesPage', () => {
  it('renders the page with upload area', () => {
    render(<ResumesPage />);

    expect(screen.getByText('Resumes')).toBeInTheDocument();
    expect(screen.getByText('Upload and manage your resumes')).toBeInTheDocument();
  });

  it('shows drag and drop instructions', () => {
    render(<ResumesPage />);

    expect(screen.getByText(/drag and drop your resume here/i)).toBeInTheDocument();
    // The actual text is "Supports PDF, DOC, DOCX (max 10MB)"
    expect(screen.getByText(/supports pdf, doc, docx/i)).toBeInTheDocument();
  });

  it('shows empty state when no resumes', () => {
    render(<ResumesPage />);

    expect(screen.getByText('No resumes uploaded yet')).toBeInTheDocument();
    expect(screen.getByText('Upload your first resume to get started')).toBeInTheDocument();
  });
});