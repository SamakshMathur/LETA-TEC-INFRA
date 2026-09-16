import { describe, it, expect } from 'vitest';
import { wasCreditedWhileModalWasOpen } from '../Payment';

/**
 * Regression coverage for a real gap found during a flow audit: Razorpay's
 * checkout modal being dismissed doesn't mean the payment failed — a UPI
 * payment in particular can confirm on the user's phone a moment AFTER the
 * modal is already closed, and the server-to-server webhook credits it
 * independently of what the browser ever saw. The old ondismiss handler
 * just reset the Pay button, so a confused customer who assumed it failed
 * could click Pay again — create-order has no idea this is a retry, so it
 * creates a brand-new order and a genuine second charge goes through.
 *
 * wasCreditedWhileModalWasOpen is the pure decision at the heart of the
 * fix: compare the plan's expiry from BEFORE this checkout attempt against
 * whatever /api/auth/me reports right after the modal closes. A later
 * expiry means it really did get credited.
 */
describe('wasCreditedWhileModalWasOpen', () => {
  it('detects a credit: session_end moved later than it was before checkout opened', () => {
    const before = Date.parse('2026-01-01T00:00:00Z');
    const after = '2026-01-01T01:00:00Z'; // an hour later — a 1hr plan just got credited
    expect(wasCreditedWhileModalWasOpen(before, after)).toBe(Date.parse(after));
  });

  it('returns null when session_end is unchanged — genuinely not credited', () => {
    const same = '2026-01-01T00:00:00Z';
    expect(wasCreditedWhileModalWasOpen(Date.parse(same), same)).toBeNull();
  });

  it('returns null when session_end moved EARLIER (stale data, not a new credit)', () => {
    const before = Date.parse('2026-01-01T02:00:00Z');
    const after = '2026-01-01T01:00:00Z';
    expect(wasCreditedWhileModalWasOpen(before, after)).toBeNull();
  });

  it('returns null when there is no session_end at all on the account', () => {
    expect(wasCreditedWhileModalWasOpen(Date.now(), null)).toBeNull();
    expect(wasCreditedWhileModalWasOpen(Date.now(), undefined)).toBeNull();
  });

  it('treats any real session_end as a credit when there was no prior plan at all', () => {
    // A brand-new customer with no plan history — previousSessionEndMs is
    // undefined, so ANY session_end reported now is new.
    const after = '2026-01-01T01:00:00Z';
    expect(wasCreditedWhileModalWasOpen(undefined, after)).toBe(Date.parse(after));
  });

  it('returns null for a malformed date string rather than throwing', () => {
    expect(wasCreditedWhileModalWasOpen(Date.now(), 'not-a-date')).toBeNull();
  });
});
