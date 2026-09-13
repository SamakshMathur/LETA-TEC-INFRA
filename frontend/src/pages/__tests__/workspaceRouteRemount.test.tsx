import { describe, it, expect } from 'vitest';
import { act, render } from '@testing-library/react';
import { useEffect, useRef } from 'react';
import { MemoryRouter, Routes, Route, useNavigate, useParams } from 'react-router-dom';

/**
 * Regression coverage for the "New Consultation snaps back to the old
 * chat" / header-double-paint bug reported live on letatec.com right
 * after per-chat URLs shipped.
 *
 * Root cause: routes/index.tsx originally defined TWO sibling Route
 * entries — "/:domainId/leta" and "/:domainId/leta/:sessionId" — both
 * rendering <LetaWorkspace/>. Two different Route matches for the same
 * element still count as two different routes to React Router: moving
 * between them fully unmounts and remounts the component, instead of
 * just updating a param on a continuously-matched route. That remount:
 *   - re-ran LetaWorkspace's mount effect, which re-reads sessionStorage's
 *     "last active session" and restores it — so clicking New
 *     Consultation (which clears state, then navigates to the id-less
 *     URL) immediately remounted straight back into the old chat.
 *   - briefly rendered the old and new component trees on top of each
 *     other mid-transition (framer-motion exit/enter overlap), which is
 *     what showed up as the header visually double-painting.
 *
 * Fix: a single route ("/:domainId/leta/*") — the session id arrives as
 * the splat param, which changes without a remount, like any other
 * in-route param transition. This test harness mirrors both route
 * shapes directly (not the real LetaWorkspace, which pulls in
 * three.js/pdf.js and is out of scope for a routing unit test) and
 * asserts the fixed shape stays mounted across exactly the navigation
 * sequence that broke in production: id-less -> real session -> back to
 * id-less (New Consultation).
 */

function Probe({ mounts, sessionIds }: { mounts: React.MutableRefObject<number>; sessionIds: string[] }) {
  const { '*': splat } = useParams();
  useEffect(() => {
    mounts.current += 1;
  }, []); // mount-only — a remount shows up as this firing again
  useEffect(() => {
    sessionIds.push(splat || '');
  }, [splat]);
  return null;
}

// Exposes react-router's navigate function to the test body via a ref,
// instead of driving navigation from inside an effect — sequencing
// several act()-wrapped navigations from the test itself is far more
// deterministic than racing an internal async loop against RTL's own
// act() flushing.
function Driver({ navigateRef }: { navigateRef: React.MutableRefObject<ReturnType<typeof useNavigate> | null> }) {
  const navigate = useNavigate();
  useEffect(() => {
    navigateRef.current = navigate;
  }, [navigate, navigateRef]);
  return null;
}

describe('workspace route shape — single-route splat vs sibling-route remount', () => {
  it('a single "/:domainId/leta/*" route stays mounted across new-chat / select-chat / new-chat again', async () => {
    const mounts = { current: 0 };
    const sessionIds: string[] = [];
    const navigateRef: React.MutableRefObject<ReturnType<typeof useNavigate> | null> = { current: null };

    render(
      <MemoryRouter initialEntries={['/gst/leta']}>
        <Routes>
          <Route path="/:domainId/leta/*" element={<Probe mounts={mounts} sessionIds={sessionIds} />} />
        </Routes>
        <Driver navigateRef={navigateRef} />
      </MemoryRouter>
    );

    const steps = ['/gst/leta/session-abc', '/gst/leta', '/gst/leta/session-xyz', '/gst/leta'];
    for (const path of steps) {
      await act(async () => { navigateRef.current!(path, { replace: true }); });
    }

    expect(mounts.current).toBe(1); // never remounted
    expect(sessionIds).toEqual(['', 'session-abc', '', 'session-xyz', '']);
  });

  it('sanity check: the ORIGINAL two-sibling-route shape really does remount (documents the bug this fix removes)', async () => {
    const mounts = { current: 0 };
    const sessionIds: string[] = [];
    const navigateRef: React.MutableRefObject<ReturnType<typeof useNavigate> | null> = { current: null };

    render(
      <MemoryRouter initialEntries={['/gst/leta']}>
        <Routes>
          <Route path="/:domainId/leta" element={<Probe mounts={mounts} sessionIds={sessionIds} />} />
          <Route path="/:domainId/leta/:sessionId" element={<ProbeWithParam mounts={mounts} sessionIds={sessionIds} />} />
        </Routes>
        <Driver navigateRef={navigateRef} />
      </MemoryRouter>
    );

    await act(async () => { navigateRef.current!('/gst/leta/session-abc', { replace: true }); });
    await act(async () => { navigateRef.current!('/gst/leta', { replace: true }); });

    // This is the bug: switching between the two sibling routes remounts.
    expect(mounts.current).toBeGreaterThan(1);
  });
});

function ProbeWithParam({ mounts, sessionIds }: { mounts: React.MutableRefObject<number>; sessionIds: string[] }) {
  const { sessionId } = useParams();
  useEffect(() => { mounts.current += 1; }, []);
  useEffect(() => { sessionIds.push(sessionId || ''); }, [sessionId]);
  return null;
}
