import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/**
 * Regression coverage for a real gap found during a UX audit: login offered
 * an "Email" method that was a guaranteed dead end — signup never collects
 * an email (phone-only), so a fresh account gets a 404 "no account found"
 * on that tab, and even an account that later added one (via Settings)
 * would silently never receive an OTP since no email provider is
 * configured yet. Phone is now the only login method offered.
 */

const loginMock = vi.fn();
const sendOtpMock = vi.fn();

vi.mock('../../../../hooks/useAuth', () => ({
  useAuth: () => ({ login: loginMock }),
}));

vi.mock('../../../../services/auth', () => ({
  sendOtpApi: (...args: any[]) => sendOtpMock(...args),
  verifyOtpApi: vi.fn(),
}));

import LoginPage from '../index';

describe('LoginPage — phone-only login', () => {
  beforeEach(() => {
    loginMock.mockClear();
    sendOtpMock.mockClear();
  });

  it('does not offer an Email method tab', () => {
    render(<MemoryRouter><LoginPage /></MemoryRouter>);
    expect(screen.queryByText('Email')).toBeNull();
    expect(screen.queryByText('Mobile')).toBeNull(); // toggle removed entirely, not just relabeled
    expect(screen.getByLabelText('Mobile Number')).toBeTruthy();
  });

  it('sends OTP with method "phone" regardless', async () => {
    sendOtpMock.mockResolvedValue({ cooldown_seconds: 60 });
    render(<MemoryRouter><LoginPage /></MemoryRouter>);

    fireEvent.change(screen.getByLabelText('Mobile Number'), { target: { value: '9876543210' } });
    fireEvent.click(screen.getByRole('button', { name: /Send OTP/i }));

    await waitFor(() => expect(sendOtpMock).toHaveBeenCalledWith('9876543210', 'phone'));
  });
});
