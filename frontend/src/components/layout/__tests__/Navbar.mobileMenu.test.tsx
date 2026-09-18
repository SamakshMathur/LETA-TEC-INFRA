import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Navbar from '../Navbar';

/**
 * Regression coverage for a real gap found during a UX audit: the entire
 * center nav (Modules/Home/About/My Docs/Admin) was `hidden md:flex` with
 * no mobile alternative anywhere — below 768px, a user lost access to
 * primary navigation entirely. Also guards against a specific bug this
 * fix could easily reintroduce: the toggle button and the global
 * outside-click-closes handler both watch mousedown/click on the same
 * element tree, and if the toggle button isn't INSIDE the same ref'd
 * container the outside-click handler checks, closing the menu via a
 * second click on the toggle button races against that handler and can
 * leave the menu stuck open instead of closing.
 */

vi.mock('../../../hooks/useAuth', () => ({
  useAuth: () => ({
    user: null,
    isLoggedIn: false,
    logout: vi.fn(),
    session: null,
  }),
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('Navbar — mobile menu', () => {
  it('is closed by default, with the hamburger toggle present', () => {
    render(<MemoryRouter><Navbar /></MemoryRouter>);
    expect(screen.queryByText('Sovereign Modules')).toBeNull();
    expect(screen.getByLabelText('Open menu')).toBeTruthy();
  });

  it('opens on click, revealing the modules and nav links', () => {
    render(<MemoryRouter><Navbar /></MemoryRouter>);
    fireEvent.click(screen.getByLabelText('Open menu'));
    // "Sovereign Modules" and the module list only ever render inside the
    // mobile panel (the desktop equivalent is gated behind its own
    // separate dropdown toggle, closed by default) — an unambiguous check
    // that the panel's real content is actually present, not just an
    // empty shell.
    expect(screen.getByText('Sovereign Modules')).toBeTruthy();
    expect(screen.getByText('GST Intelligence')).toBeTruthy();
  });

  it('closes again on a second click of the same toggle button (no stuck-open race with the outside-click handler)', () => {
    render(<MemoryRouter><Navbar /></MemoryRouter>);

    // Open
    fireEvent.mouseDown(screen.getByLabelText('Open menu'));
    fireEvent.click(screen.getByLabelText('Open menu'));
    expect(screen.getByText('Sovereign Modules')).toBeTruthy();

    // Close — the same button, now labeled "Close menu". A real click
    // fires mousedown then click on the SAME element, exactly like this.
    const closeButton = screen.getByLabelText('Close menu');
    fireEvent.mouseDown(closeButton);
    fireEvent.click(closeButton);

    expect(screen.queryByText('Sovereign Modules')).toBeNull();
  });

  it('closes when clicking outside the menu', () => {
    render(<MemoryRouter><Navbar /></MemoryRouter>);
    fireEvent.click(screen.getByLabelText('Open menu'));
    expect(screen.getByText('Sovereign Modules')).toBeTruthy();

    fireEvent.mouseDown(document.body);
    expect(screen.queryByText('Sovereign Modules')).toBeNull();
  });

  it('links to the actual document library, not the unrelated marketing docs page', () => {
    render(<MemoryRouter><Navbar /></MemoryRouter>);
    fireEvent.click(screen.getByLabelText('Open menu'));
    // Both the (always-rendered, closed-by-default) desktop nav and the
    // open mobile panel have a "Library" link — assert at least one of
    // them points at the real route, same duplication jsdom shows for
    // "Home" elsewhere in this file.
    const libraryLinks = screen.getAllByText('Library').map(el => el.closest('a'));
    expect(libraryLinks.some(a => a?.getAttribute('href') === '/document-library')).toBe(true);
  });
});
