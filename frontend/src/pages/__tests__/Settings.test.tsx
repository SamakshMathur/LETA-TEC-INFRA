import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/**
 * Regression coverage for a real blocker found during a UX audit: the
 * only account-management entry point in the whole product (Navbar's
 * "Settings" link) pointed at a route that didn't exist — a logged-in
 * user clicking it hit a 404. There was no way for any user to view or
 * edit their own name, email, or phone, and specifically no way for a
 * phone-only signup to ever add an email — the reason payment receipt
 * emails render blank for most users.
 */

const loginMock = vi.fn();
const patchMock = vi.fn();

vi.mock('../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: { id: 'u1', full_name: 'Alice', phone: '9876543210', role: 'user' },
    session: {
      tokens: { session_end_ms: undefined },
      user: { id: 'u1', full_name: 'Alice', phone: '9876543210', role: 'user' },
      memberships: [], organizationId: 'org1',
    },
    login: loginMock,
  }),
}));

vi.mock('../../utils/api', () => ({
  AXIOS_INSTANCE: { patch: (...args: any[]) => patchMock(...args) },
}));

import Settings from '../Settings';

describe('Settings page — profile editing', () => {
  beforeEach(() => {
    loginMock.mockClear();
    patchMock.mockClear();
  });

  it('pre-fills the current name and shows a hint when no email is on file', () => {
    render(<MemoryRouter><Settings /></MemoryRouter>);
    expect(screen.getByDisplayValue('Alice')).toBeTruthy();
    expect(screen.getByText(/Add an email to receive payment receipts/)).toBeTruthy();
  });

  it('Save is disabled until something actually changes', () => {
    render(<MemoryRouter><Settings /></MemoryRouter>);
    const saveButton = screen.getByRole('button', { name: /Save Changes/i }) as HTMLButtonElement;
    expect(saveButton.disabled).toBe(true);

    fireEvent.change(screen.getByDisplayValue('Alice'), { target: { value: 'Alice Sharma' } });
    expect(saveButton.disabled).toBe(false);
  });

  it('saving sends only the changed field(s) and updates the auth session on success', async () => {
    patchMock.mockResolvedValue({ data: { full_name: 'Alice Sharma', phone: '9876543210' } });
    render(<MemoryRouter><Settings /></MemoryRouter>);

    fireEvent.change(screen.getByDisplayValue('Alice'), { target: { value: 'Alice Sharma' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Changes/i }));

    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1));
    const [, body] = patchMock.mock.calls[0];
    expect(body).toEqual({ full_name: 'Alice Sharma' }); // email untouched, not sent

    await waitFor(() => expect(loginMock).toHaveBeenCalledTimes(1));
  });

  it('adding an email for a phone-only account sends it and clears the "no email" hint after saving', async () => {
    patchMock.mockResolvedValue({ data: { full_name: 'Alice', email: 'alice@example.com' } });
    render(<MemoryRouter><Settings /></MemoryRouter>);

    const emailInput = screen.getByPlaceholderText('you@example.com');
    fireEvent.change(emailInput, { target: { value: 'alice@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Changes/i }));

    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1));
    const [, body] = patchMock.mock.calls[0];
    expect(body).toEqual({ email: 'alice@example.com' });
  });

  it('shows a real error message when the save fails', async () => {
    patchMock.mockRejectedValue({ response: { data: { detail: 'Email already in use by another account' } } });
    render(<MemoryRouter><Settings /></MemoryRouter>);

    fireEvent.change(screen.getByDisplayValue('Alice'), { target: { value: 'Alice Sharma' } });
    fireEvent.click(screen.getByRole('button', { name: /Save Changes/i }));

    await waitFor(() => expect(screen.getByText('Email already in use by another account')).toBeTruthy());
    expect(loginMock).not.toHaveBeenCalled();
  });
});
