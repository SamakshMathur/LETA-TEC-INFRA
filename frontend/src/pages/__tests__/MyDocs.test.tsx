import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/**
 * Regression coverage for a real dead link found while wiring up the
 * document library: MyDocs' empty state has always pointed "Browse
 * Document Library" at "/docs", but that path renders the unrelated
 * marketing Documentation page — DocumentLibrary.tsx (a fully-built,
 * already-working component: search, category rows, circulars/
 * notifications year-tabs) had no route at all until this fix. Same bug
 * class as the dead footer links (#70) and the 404'd Settings link (#69).
 */

vi.mock('../../hooks/useSavedDocs', () => ({
  useSavedDocs: () => ({ saved: [], toggle: vi.fn(), clear: vi.fn() }),
}));

import MyDocs from '../MyDocs';

describe('MyDocs — empty state entry point', () => {
  it('"Browse Document Library" points at the real document library route', () => {
    render(<MemoryRouter><MyDocs /></MemoryRouter>);
    const link = screen.getByText('Browse Document Library').closest('a');
    expect(link?.getAttribute('href')).toBe('/document-library');
  });
});
