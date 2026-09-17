import { describe, it, expect } from 'vitest';
import { buildSupportMailtoHref } from '../Payment';
import { CONTACT_EMAIL } from '../../constants/contact';

/**
 * Regression coverage for a real gap found during a UX audit: when a
 * genuine payment failure occurred (Razorpay actually charged the card,
 * our own /verify rejected it), the error message told the customer to
 * "contact support with your payment ID" but gave no actual way to do
 * that — the only support address in the whole product lived three
 * clicks away in Terms & Conditions. buildSupportMailtoHref is the fix:
 * a real mailto link with the payment ID embedded in the body, so the
 * customer doesn't have to go hunting or retype anything at the exact
 * moment their card was just charged and something went wrong.
 */
describe('buildSupportMailtoHref', () => {
  it('points at the real support address', () => {
    expect(buildSupportMailtoHref('pay_abc123')).toContain(`mailto:${CONTACT_EMAIL}`);
  });

  it('embeds the payment ID in the body, not just leaves it to the user to type', () => {
    const href = buildSupportMailtoHref('pay_abc123');
    expect(decodeURIComponent(href)).toContain('Payment ID: pay_abc123');
  });

  it('produces a well-formed mailto URL with subject and body params', () => {
    const href = buildSupportMailtoHref('pay_xyz789');
    expect(href).toMatch(/^mailto:[^?]+\?subject=.+&body=.+$/);
  });
});
