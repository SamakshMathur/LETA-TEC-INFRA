import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SystemFooter from '../SystemFooter';

/**
 * Regression coverage for a real trust-signal issue found during a UX
 * audit: the footer's social icons and "API Reference"/"System Status"
 * links all pointed at href="#" — present on both the checkout page and
 * the dashboard, a hesitant first-time payer scanning for legitimacy
 * signals ran into dead links. Removed rather than faked with a real-
 * looking but nonexistent destination.
 */
describe('SystemFooter — no dead links', () => {
  it('has no href="#" or to="#" links anywhere', () => {
    const { container } = render(<MemoryRouter><SystemFooter /></MemoryRouter>);
    const deadLinks = Array.from(container.querySelectorAll('a')).filter(
      a => a.getAttribute('href') === '#'
    );
    expect(deadLinks).toHaveLength(0);
  });

  it('does not render "API Reference" or "System Status" labels with no real destination', () => {
    render(<MemoryRouter><SystemFooter /></MemoryRouter>);
    expect(screen.queryByText('API Reference')).toBeNull();
    expect(screen.queryByText('System Status')).toBeNull();
  });

  it('still renders the real, working resource links', () => {
    render(<MemoryRouter><SystemFooter /></MemoryRouter>);
    expect(screen.getByText('Documentation')).toBeTruthy();
    expect(screen.getByText('About Us')).toBeTruthy();
    expect(screen.getByText('Legal Policies')).toBeTruthy();
  });
});
