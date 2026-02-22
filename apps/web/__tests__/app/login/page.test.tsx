import { render, screen } from '@testing-library/react';
import LoginPage from '@/app/login/page';

// Mock the useAuth hook used by the page
jest.mock('@/lib/auth', () => ({
  useAuth: () => ({
    user: null,
    login: jest.fn().mockResolvedValue(undefined),
    isLoading: false,
  }),
}));

describe('LoginPage', () => {
  it('renders login form', () => {
    render(<LoginPage />);

    expect(screen.getByText(/sign in to your account/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('has email input field', () => {
    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/email/i);
    expect(emailInput).toHaveAttribute('type', 'email');
  });

  it('has password input field', () => {
    render(<LoginPage />);

    const passwordInput = screen.getByLabelText(/password/i);
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  it('has submit button', () => {
    render(<LoginPage />);

    const submitButton = screen.getByRole('button', { name: /sign in/i });
    expect(submitButton).toBeInTheDocument();
  });
});