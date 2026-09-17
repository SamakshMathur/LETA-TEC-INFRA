import { describe, it, expect } from 'vitest';
import { maskContact } from '../index';

/**
 * Regression coverage for a real bug found during a UX audit: the OTP
 * confirmation line always rendered "+91 ••••••{last 4 chars}" regardless
 * of which method (phone or email) the user picked. Choosing the Email
 * tab and entering an address rendered something like "+91 ••••••e.com" —
 * a phone-formatted mask wrapped around an email, right at the identity-
 * verification step where a wrong-looking confirmation is most alarming.
 */
describe('maskContact', () => {
  it('phone method masks as +91 with the last 4 digits visible', () => {
    expect(maskContact('9876543210', 'phone')).toBe('+91 ••••••3210');
  });

  it('email method masks the local part, keeps the domain fully visible', () => {
    expect(maskContact('alice@example.com', 'email')).toBe('al•••@example.com');
  });

  it('email method never produces a phone-style "+91" prefix', () => {
    const masked = maskContact('alice@example.com', 'email');
    expect(masked).not.toContain('+91');
  });

  it('handles a very short local part without a negative repeat count', () => {
    expect(() => maskContact('a@b.com', 'email')).not.toThrow();
    expect(maskContact('a@b.com', 'email')).toBe('a••@b.com');
  });

  it('falls back to showing the raw string for a malformed email (no @)', () => {
    expect(maskContact('not-an-email', 'email')).toBe('not-an-email');
  });
});
