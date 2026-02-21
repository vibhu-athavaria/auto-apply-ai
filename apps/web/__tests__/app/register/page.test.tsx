import { render, screen } from '@testing-library/react';
import RegisterPage from '@/app/register/page';

// Mock the useAuth hook used by the page
jest.mock('@/lib/auth', () => ({
  useAuth: () => ({
    user: null,
    login: jest.fn().mockResolvedValue(undefined),
    isLoading: false,
  }),
}));

describe('RegisterPage', () => {
  it('renders registration form', () => {
    render(<RegisterPage />);

    expect(screen.getByText('Create your account')).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
  });

  it('renders link to login page', () => {
    render(<RegisterPage />);

    expect(screen.getByText(/already have an account/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /sign in/i })).toBeInTheDocument();
  });

  it('has email input field', () => {
    render(<RegisterPage />);

    const emailInput = screen.getByLabelText(/email/i);
    expect(emailInput).toHaveAttribute('type', 'email');
  });

  it('has password input fields', () => {
    render(<RegisterPage />);

    // There are two password fields - password and confirm password
    const passwordInputs = screen.getAllByLabelText(/password/i);
    expect(passwordInputs.length).toBeGreaterThanOrEqual(1);
  });

  it('has submit button', () => {
    render(<RegisterPage />);

    const submitButton = screen.getByRole('button', { name: /create account/i });
    expect(submitButton).toBeInTheDocument();
  });
});