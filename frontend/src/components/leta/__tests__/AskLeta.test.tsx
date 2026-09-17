import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

/**
 * Regression coverage for a real integrity issue found during a UX audit:
 * this dashboard "Advisory Briefing Suite" widget hardcoded a confidence
 * score of 0.92 on every successful response regardless of the actual
 * answer's quality (and 0 on error) — a fabricated per-answer trust
 * signal that never even reached the screen (ConfidenceBadge exists in
 * this codebase but was never wired in here), but sat in the response
 * object as latent fake data ready to mislead a user the moment anyone
 * wired a badge up to it. Removed rather than displayed, since there is
 * no real per-answer confidence score to show.
 */

let capturedProps: any = null;
vi.mock('../LetaResponse', () => ({
  default: (props: any) => {
    capturedProps = props;
    return <div data-testid="leta-response-mock" />;
  },
}));

import AskLeta from '../AskLeta';

describe('AskLeta — no fabricated confidence score', () => {
  beforeEach(() => {
    capturedProps = null;
    vi.restoreAllMocks();
  });

  it('does not include a confidence field on a successful response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ answer: 'The ITC is available.', sources: [{ title: 'Section 16' }] }),
    }));

    render(<AskLeta />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Is ITC available?' } });
    fireEvent.click(screen.getByRole('button', { name: /ask|submit|analy/i }));

    await waitFor(() => expect(screen.getByTestId('leta-response-mock')).toBeTruthy());
    expect(capturedProps.data).not.toHaveProperty('confidence');
    expect(capturedProps.data.answer).toBe('The ITC is available.');
  });

  it('does not include a confidence field on a failed/error response either', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')));

    render(<AskLeta />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Is ITC available?' } });
    fireEvent.click(screen.getByRole('button', { name: /ask|submit|analy/i }));

    await waitFor(() => expect(screen.getByTestId('leta-response-mock')).toBeTruthy());
    expect(capturedProps.data).not.toHaveProperty('confidence');
  });
});
