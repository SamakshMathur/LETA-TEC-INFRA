import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { formatRupees, formatIssuedDate } from '../InvoiceHistory';

/**
 * Regression coverage for a real gap found while auditing launch
 * readiness: a "should fix soon" item deferred until the Settings page
 * (#69) shipped, since invoice history builds on it. Before this, the
 * ONLY way to ever see an invoice was the Download Invoice button on the
 * Payment success screen, immediately after paying — there was no way to
 * come back later and get a past invoice again.
 */

const getMock = vi.fn();

vi.mock('../../utils/api', () => ({
  AXIOS_INSTANCE: { get: (...args: any[]) => getMock(...args) },
}));

import InvoiceHistory from '../InvoiceHistory';

const invoice = {
  invoice_number: 'LETA/2026-27/00007',
  payment_id: 'pay_abc123',
  plan_name: '1-Hour Access',
  amount_paise: 1000,
  issued_at: '2026-06-15T10:00:00Z',
};

describe('formatRupees', () => {
  it('formats whole-rupee amounts without decimal noise', () => {
    expect(formatRupees(1000)).toBe('Rs.10');
  });
});

describe('formatIssuedDate', () => {
  it('formats an ISO timestamp as a readable date', () => {
    expect(formatIssuedDate('2026-06-15T10:00:00Z')).toMatch(/2026/);
  });
});

describe('InvoiceHistory page', () => {
  beforeEach(() => {
    getMock.mockClear();
    vi.stubGlobal('fetch', vi.fn());
  });

  it('shows a loading state, then the fetched invoices', async () => {
    getMock.mockResolvedValue({ data: [invoice] });
    render(<MemoryRouter><InvoiceHistory /></MemoryRouter>);

    expect(screen.getByText(/Loading invoices/)).toBeTruthy();

    await waitFor(() => expect(screen.getByText('1-Hour Access')).toBeTruthy());
    expect(screen.getByText(/LETA\/2026-27\/00007/)).toBeTruthy();
    expect(screen.getByText('Rs.10')).toBeTruthy();
  });

  it('shows an empty state when the user has no invoices', async () => {
    getMock.mockResolvedValue({ data: [] });
    render(<MemoryRouter><InvoiceHistory /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/No invoices yet/)).toBeTruthy());
  });

  it('shows an error message if the list fails to load', async () => {
    getMock.mockRejectedValue(new Error('network down'));
    render(<MemoryRouter><InvoiceHistory /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/Could not load your invoice history/)).toBeTruthy());
  });

  it('downloading an invoice calls the per-payment download endpoint', async () => {
    getMock.mockResolvedValue({ data: [invoice] });
    (global.fetch as any).mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(['%PDF-'])),
      headers: { get: () => 'attachment; filename="LETA-2026-27-00007.pdf"' },
    });
    // jsdom doesn't implement object URLs — stub them so the download path
    // (createObjectURL/revokeObjectURL) doesn't throw.
    (URL as any).createObjectURL = vi.fn(() => 'blob:mock');
    (URL as any).revokeObjectURL = vi.fn();

    render(<MemoryRouter><InvoiceHistory /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText('1-Hour Access')).toBeTruthy());

    fireEvent.click(screen.getByLabelText('Download invoice LETA/2026-27/00007'));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/payments/invoice/pay_abc123'),
      expect.anything(),
    ));
  });
});
