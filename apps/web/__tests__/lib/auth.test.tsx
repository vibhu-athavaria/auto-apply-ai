import { render, screen } from '@testing-library/react';
import { AuthProvider, useAuth } from '@/lib/auth';

// Test component to access auth context
function TestComponent() {
  const { user, isLoading } = useAuth();
  return (
    <div>
      <span data-testid="user">{user?.email || 'no-user'}</span>
      <span data-testid="loading">{isLoading.toString()}</span>
    </div>
  );
}

describe('AuthContext', () => {
  beforeEach(() => {
    Storage.prototype.getItem = jest.fn(() => null);
    Storage.prototype.setItem = jest.fn();
    Storage.prototype.removeItem = jest.fn();
  });

  it('provides initial state with no user', () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('user')).toHaveTextContent('no-user');
  });

  it('provides loading state', () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    expect(screen.getByTestId('loading')).toHaveTextContent('false');
  });
});
