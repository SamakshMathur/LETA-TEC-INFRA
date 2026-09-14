import { describe, it, expect } from 'vitest';
import { classifyPaymentVerifyResult } from '../Payment';

/**
 * Regression coverage for a live incident: a real customer's payment
 * genuinely succeeded (credited via Razorpay's server-to-server webhook,
 * which beat the browser's own POST /api/payments/verify call in a race —
 * both paths are meant to succeed regardless of which lands first) but
 * the checkout UI showed "Payment verification failed. Please contact
 * support with your payment ID." — because the frontend treated /verify's
 * 409 (idempotency correctly rejecting an already-claimed payment_id) as
 * a plain failure, identical to a genuine error.
 */
describe('classifyPaymentVerifyResult', () => {
  it('200 is a plain success', () => {
    expect(classifyPaymentVerifyResult(200)).toBe('success');
  });

  it('409 is a duplicate — already credited via the other path, not a failure', () => {
    expect(classifyPaymentVerifyResult(409)).toBe('duplicate');
  });

  it('401 is a session-expired-during-checkout case, distinct from a real failure', () => {
    expect(classifyPaymentVerifyResult(401)).toBe('session-expired');
  });

  it('any other status is a genuine failure', () => {
    expect(classifyPaymentVerifyResult(500)).toBe('failed');
    expect(classifyPaymentVerifyResult(400)).toBe('failed');
    expect(classifyPaymentVerifyResult(503)).toBe('failed');
  });
});
