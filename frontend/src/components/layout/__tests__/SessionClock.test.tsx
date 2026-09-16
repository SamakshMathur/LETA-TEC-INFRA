import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SessionClock from '../SessionClock';

/**
 * Regression coverage for a real launch-day incident: a customer completing
 * a Razorpay payment got yanked to /login mid-checkout, right as their
 * payment was going through.
 *
 * Root cause: SessionClock is mounted globally (via Navbar, rendered at the
 * app root outside the route switch), and counts down the OLD plan's
 * session_end_ms independent of whatever page is showing. A user visiting
 * /payment specifically because their old plan already expired would have
 * that countdown hit zero while they were mid-Razorpay-checkout (entering
 * card details / waiting on a bank OTP genuinely takes a minute or two),
 * firing a forced logout() + navigate('/login') that unmounted the Payment
 * page — losing the /verify success state — regardless of whether the
 * payment itself succeeded.
 *
 * Fix: suppress the auto-logout-and-redirect while on the payment route.
 * These tests assert both halves: the redirect is suppressed there, and
 * still fires normally everywhere else (so the fix doesn't quietly disable
 * expiry handling app-wide).
 */

const logoutMock = vi.fn();

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: () => ({
    session: {
      tokens: { session_end_ms: Date.now() - 1000 }, // already expired
      user: { plan: 'pro' },
    },
    logout: logoutMock,
  }),
}));

beforeEach(() => {
  logoutMock.mockClear();
});

describe('SessionClock — expiry redirect suppressed on the payment page', () => {
  it('does NOT log out or redirect while on /payment, even with an already-expired old session', () => {
    render(
      <MemoryRouter initialEntries={['/payment?module=gst&plan=1hr']}>
        <SessionClock />
      </MemoryRouter>
    );

    expect(logoutMock).not.toHaveBeenCalled();
  });

  it('still logs out and redirects on other pages when the session has expired (unchanged behavior)', () => {
    render(
      <MemoryRouter initialEntries={['/gst/leta']}>
        <SessionClock />
      </MemoryRouter>
    );

    expect(logoutMock).toHaveBeenCalledTimes(1);
  });
});
