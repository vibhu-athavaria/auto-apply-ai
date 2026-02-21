import { render, screen } from '@testing-library/react';
import DashboardLayout from '@/components/DashboardLayout';

// Mock the useAuth hook
jest.mock('@/lib/auth', () => ({
  useAuth: () => ({
    user: { email: 'test@example.com' },
    logout: jest.fn(),
  }),
}));

describe('DashboardLayout', () => {
  it('renders children correctly', () => {
    render(
      <DashboardLayout>
        <div>Test Content</div>
      </DashboardLayout>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('renders navigation links', () => {
    render(
      <DashboardLayout>
        <div>Content</div>
      </DashboardLayout>
    );

    // Use getAllByText since there are mobile and desktop versions
    const dashboardLinks = screen.getAllByText('Dashboard');
    expect(dashboardLinks.length).toBeGreaterThan(0);

    const resumesLinks = screen.getAllByText('Resumes');
    expect(resumesLinks.length).toBeGreaterThan(0);

    // The navigation item is "Job Profiles" not "Profiles"
    const jobProfilesLinks = screen.getAllByText('Job Profiles');
    expect(jobProfilesLinks.length).toBeGreaterThan(0);

    const jobsLinks = screen.getAllByText('Jobs');
    expect(jobsLinks.length).toBeGreaterThan(0);
  });

  it('renders user email in sidebar', () => {
    render(
      <DashboardLayout>
        <div>Content</div>
      </DashboardLayout>
    );

    // Use getAllByText since email may appear multiple times
    const userEmails = screen.getAllByText('test@example.com');
    expect(userEmails.length).toBeGreaterThan(0);
  });
});
