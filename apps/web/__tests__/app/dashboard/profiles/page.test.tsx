import { render, screen, waitFor } from '@testing-library/react';
import ProfilesPage from '@/app/dashboard/profiles/page';

// Mock the DashboardLayout component
jest.mock('@/components/DashboardLayout', () => {
  return function MockDashboardLayout({ children }: { children: React.ReactNode }) {
    return <div data-testid="dashboard-layout">{children}</div>;
  };
});

// Mock the API
jest.mock('@/lib/api', () => ({
  profileApi: {
    list: jest.fn().mockResolvedValue([]),
    create: jest.fn().mockResolvedValue({}),
    delete: jest.fn().mockResolvedValue({}),
  },
}));

describe('ProfilesPage', () => {
  it('renders the page with header', () => {
    render(<ProfilesPage />);

    expect(screen.getByText('Job Search Profiles')).toBeInTheDocument();
    expect(screen.getByText('Define your job search preferences')).toBeInTheDocument();
  });

  it('shows new profile button', () => {
    render(<ProfilesPage />);

    // The button text is "New Profile"
    expect(screen.getByText('New Profile')).toBeInTheDocument();
  });

  it('shows empty state when no profiles', async () => {
    render(<ProfilesPage />);

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.getByText('No search profiles yet')).toBeInTheDocument();
    });

    expect(screen.getByText('Create a profile to start finding jobs')).toBeInTheDocument();
  });
});