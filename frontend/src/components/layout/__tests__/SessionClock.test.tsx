import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
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
 *
 * Also covers a second, separate flow-audit finding: the moment of expiry
 * was previously a silent, instant logout with ZERO advance warning beyond
 * a small badge color change (easy to miss in a corner while composing a
 * message) — killing an in-flight chat/upload with no notice. A warning
 * toast now appears in the last two minutes with a "Renew now" CTA.
 */

const logoutMock = vi.fn();
let mockSessionEndMs = Date.now() - 1000;

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: () => ({
    session: {
      tokens: { session_end_ms: mockSessionEndMs },
      user: { plan: 'pro' },
    },
    logout: logoutMock,
  }),
}));

beforeEach(() => {
  logoutMock.mockClear();
  mockSessionEndMs = Date.now() - 1000;
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

describe('SessionClock — advance warning toast before the hard cutoff', () => {
  it('shows a "Renew now" warning toast in the last two minutes', () => {
    mockSessionEndMs = Date.now() + 90 * 1000; // 90s left — inside the 120s warning window
    render(
      <MemoryRouter initialEntries={['/gst/leta']}>
        <SessionClock />
      </MemoryRouter>
    );

    expect(screen.getByRole('alert')).toBeTruthy();
    expect(screen.getByText('Renew now')).toBeTruthy();
  });

  it('does not show the toast when more than two minutes remain', () => {
    mockSessionEndMs = Date.now() + 10 * 60 * 1000; // 10 min left
    render(
      <MemoryRouter initialEntries={['/gst/leta']}>
        <SessionClock />
      </MemoryRouter>
    );

    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('the toast is dismissible and stays dismissed', () => {
    mockSessionEndMs = Date.now() + 90 * 1000;
    render(
      <MemoryRouter initialEntries={['/gst/leta']}>
        <SessionClock />
      </MemoryRouter>
    );

    expect(screen.getByRole('alert')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Dismiss'));
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('never shows the toast on the payment page itself', () => {
    mockSessionEndMs = Date.now() + 90 * 1000;
    render(
      <MemoryRouter initialEntries={['/payment']}>
        <SessionClock />
      </MemoryRouter>
    );

    expect(screen.queryByRole('alert')).toBeNull();
  });
});
