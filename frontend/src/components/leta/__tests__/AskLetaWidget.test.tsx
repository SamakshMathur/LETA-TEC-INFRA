import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { hasActivePlan } from '../AskLetaWidget';

/**
 * Regression coverage for a real, severe security gap: this card (the
 * "Start LETA TEC Consultation" / "Enter Workspace" tile on a module's hub
 * page, e.g. /gst) linked straight into `/${domain}/leta` unconditionally —
 * no plan check at all. Any signed-up user, paid or not, could reach the
 * workspace and call /ask directly this way. Unlike ModuleDashboard.tsx's
 * own "Enter Workspace" card (the /dashboard equivalent), which always
 * routes a non-admin through /payment first, this one had no such gate.
 *
 * Fixed alongside a matching gap in the backend's own _verify_plan_active
 * (rag-backend/app/api/app.py), which used to let a user with no
 * session_end on record through unconditionally — the real security
 * boundary, but this frontend fix is still real: it's the difference
 * between a confusing 401 mid-conversation and a clean redirect to pay.
 */

describe('hasActivePlan', () => {
  it('is false with no session_end_ms at all (never paid)', () => {
    expect(hasActivePlan(undefined, Date.now())).toBe(false);
  });

  it('is false once session_end_ms is in the past', () => {
    expect(hasActivePlan(Date.now() - 1000, Date.now())).toBe(false);
  });

  it('is true while session_end_ms is still in the future', () => {
    expect(hasActivePlan(Date.now() + 1000 * 60 * 60, Date.now())).toBe(true);
  });
});

const mockUseAuth = vi.fn();
vi.mock('../../../hooks/useAuth', () => ({
  useAuth: () => mockUseAuth(),
}));

import AskLetaWidget from '../AskLetaWidget';

describe('AskLetaWidget — routing depends on actually having an active plan', () => {
  it('sends a user with no plan to /payment, not straight into the workspace', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'user' }, session: { tokens: {} } });
    render(<MemoryRouter><AskLetaWidget domain="gst" /></MemoryRouter>);
    const link = screen.getByText('Start LETA TEC Consultation').closest('a');
    expect(link?.getAttribute('href')).toBe('/payment?module=gst');
    expect(screen.getByText('Continue to Payment')).toBeTruthy();
  });

  it('sends a user with an active plan straight into the workspace', () => {
    mockUseAuth.mockReturnValue({
      user: { role: 'user' },
      session: { tokens: { session_end_ms: Date.now() + 1000 * 60 * 60 } },
    });
    render(<MemoryRouter><AskLetaWidget domain="gst" /></MemoryRouter>);
    const link = screen.getByText('Start LETA TEC Consultation').closest('a');
    expect(link?.getAttribute('href')).toBe('/gst/leta');
    expect(screen.getByText('Enter Workspace')).toBeTruthy();
  });

  it('sends an admin straight into the workspace regardless of plan', () => {
    mockUseAuth.mockReturnValue({ user: { role: 'admin' }, session: { tokens: {} } });
    render(<MemoryRouter><AskLetaWidget domain="gst" /></MemoryRouter>);
    const link = screen.getByText('Start LETA TEC Consultation').closest('a');
    expect(link?.getAttribute('href')).toBe('/gst/leta');
  });
});
