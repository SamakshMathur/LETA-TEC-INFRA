import { describe, it, expect } from 'vitest';
import { act, render, waitFor } from '@testing-library/react';
import { useEffect, useRef, useState } from 'react';

/**
 * Regression coverage for the new-session streaming handoff bug.
 *
 * Root cause: `handleAsk` in LetaWorkspace.tsx is a long-lived async
 * closure spanning an entire streaming request. Every reference to
 * `currentSessionId` inside it is captured at call time; later
 * `setCurrentSessionId()` calls made during that same execution (once
 * a brand-new session gets its real backend UUID) never update that
 * closure-local binding — that's just how JS closures work. The three
 * gating checks (`updateStreamMessages`, `setStreamLoading`,
 * `setStreamStreaming`) compared that stale value against
 * `streamSessionKey`, so once `streamSessionKey` was reassigned to the
 * real UUID after session creation, the check could never be true
 * again for the rest of that stream: content kept saving to the ref
 * and the backend, but never reached the screen.
 *
 * The fix is a ref (`currentSessionIdRef`) kept live via a
 * `useEffect`, read by the gating checks instead of the frozen state
 * value. These tests exercise that exact pattern in isolation — a
 * minimal harness reproducing handleAsk's session bookkeeping — since
 * mounting the full LetaWorkspace component (three.js / pdf viewer /
 * API client tree) is out of scope for this regression test.
 */

type Message = { role: 'user' | 'assistant'; content: string };

function useStreamingHarness() {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const sessionMessagesRef = useRef<Map<string, Message[]>>(new Map());

  const currentSessionIdRef = useRef<string | null>(currentSessionId);
  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  // Mirrors handleAsk: creates a session (or fails), then streams
  // chunks in, gated on the *live* session id via the ref.
  async function handleAsk(opts: {
    createSession: () => Promise<string>;
    chunks: string[];
    existingSessionId?: string | null;
    chunkDelayMs?: number;
  }) {
    let streamSessionKey = opts.existingSessionId ?? `pending-${Date.now()}`;
    sessionMessagesRef.current.set(streamSessionKey, [{ role: 'user', content: 'hi' }]);

    const updateStreamMessages = (updater: (prev: Message[]) => Message[]) => {
      const previous = sessionMessagesRef.current.get(streamSessionKey) || [];
      const next = updater(previous);
      sessionMessagesRef.current.set(streamSessionKey, next);
      if (currentSessionIdRef.current === streamSessionKey) setMessages(next);
    };
    const setStreamLoading = (value: boolean) => {
      if (currentSessionIdRef.current === streamSessionKey) setIsLoading(value);
    };
    const setStreamStreaming = (value: boolean) => {
      if (currentSessionIdRef.current === streamSessionKey) setIsStreaming(value);
    };

    setStreamLoading(true);

    if (!opts.existingSessionId) {
      try {
        const realId = await opts.createSession();
        // Migrate buffered messages from the placeholder key to the real one.
        const buffered = sessionMessagesRef.current.get(streamSessionKey) || [];
        sessionMessagesRef.current.delete(streamSessionKey);
        streamSessionKey = realId;
        sessionMessagesRef.current.set(streamSessionKey, buffered);
        setCurrentSessionId(realId);
        // A real stream's next chunk arrives via an awaited network read
        // (fetch body reader / EventSource). React's passive effects
        // (the ref-sync useEffect) flush on a macrotask, not a
        // microtask, so mirror that with a real setTimeout(0) yield
        // rather than asserting the buggy "state applied fully
        // synchronously" assumption.
        await new Promise(resolve => setTimeout(resolve, 0));
      } catch {
        setCurrentSessionId(null);
        setStreamLoading(false);
        return;
      }
    }

    setStreamStreaming(true);
    updateStreamMessages(prev => [...prev, { role: 'assistant', content: '' }]);
    for (const chunk of opts.chunks) {
      await new Promise(resolve => setTimeout(resolve, opts.chunkDelayMs ?? 0)); // simulate awaited network read of the next chunk (macrotask, matches real passive-effect flush timing)
      updateStreamMessages(prev => {
        const next = [...prev];
        next[next.length - 1] = { ...next[next.length - 1], content: next[next.length - 1].content + chunk };
        return next;
      });
    }
    setStreamStreaming(false);
    setStreamLoading(false);
  }

  return { currentSessionId, messages, isLoading, isStreaming, handleAsk, setCurrentSessionId };
}

function Harness({ onReady }: { onReady: (api: ReturnType<typeof useStreamingHarness>) => void }) {
  const api = useStreamingHarness();
  onReady(api);
  return <div data-testid="messages">{api.messages.map(m => m.content).join('|')}</div>;
}

// Note: these tests deliberately do NOT wrap the multi-chunk `handleAsk`
// calls in RTL's `act()`. `act()` intentionally defers ALL effect
// flushing (including the ref-sync useEffect under test) until its
// entire callback settles, which would make every chunk see the same
// stale ref and mask exactly the bug this file exists to catch. Plain
// `await` lets each real macrotask commit and flush effects as it would
// in the browser; `waitFor` polls for the eventually-consistent result.
describe('new-session streaming handoff', () => {
  it('renders streamed content once a brand-new session gets its real backend id', async () => {
    let api!: ReturnType<typeof useStreamingHarness>;
    render(<Harness onReady={a => (api = a)} />);

    await api.handleAsk({
      createSession: () => Promise.resolve('real-uuid-123'),
      chunks: ['Hello', ' ', 'world'],
    });

    await waitFor(() => {
      expect(api.messages.map(m => m.content).join('')).toContain('Hello world');
    });
    expect(api.currentSessionId).toBe('real-uuid-123');
    expect(api.isLoading).toBe(false);
    expect(api.isStreaming).toBe(false);
  });

  it('resets session state cleanly when session creation fails (no orphaned optimistic id)', async () => {
    let api!: ReturnType<typeof useStreamingHarness>;
    render(<Harness onReady={a => (api = a)} />);

    await api.handleAsk({
      createSession: () => Promise.reject(new Error('network error')),
      chunks: ['should not render'],
    });

    await waitFor(() => {
      expect(api.currentSessionId).toBeNull();
      expect(api.isLoading).toBe(false);
    });
    expect(api.messages.map(m => m.content).join('')).not.toContain('should not render');
  });

  it('succeeds on retry after a prior session-creation failure', async () => {
    let api!: ReturnType<typeof useStreamingHarness>;
    render(<Harness onReady={a => (api = a)} />);

    await api.handleAsk({
      createSession: () => Promise.reject(new Error('network error')),
      chunks: ['first attempt'],
    });
    await waitFor(() => {
      expect(api.currentSessionId).toBeNull();
    });

    await api.handleAsk({
      createSession: () => Promise.resolve('real-uuid-456'),
      chunks: ['second', ' attempt'],
    });

    await waitFor(() => {
      expect(api.messages.map(m => m.content).join('')).toContain('second attempt');
    });
    expect(api.currentSessionId).toBe('real-uuid-456');
  });

  it('does not leak a stream into the wrong session when the user switches sessions mid-stream', async () => {
    let api!: ReturnType<typeof useStreamingHarness>;
    render(<Harness onReady={a => (api = a)} />);

    // The user is already viewing session A when the stream starts.
    act(() => {
      api.setCurrentSessionId('session-A');
    });
    await waitFor(() => {
      expect(api.currentSessionId).toBe('session-A');
    });

    const streamPromise = api.handleAsk({
      existingSessionId: 'session-A',
      createSession: () => Promise.resolve('unused'),
      chunks: ['chunk-A-1', 'chunk-A-2'],
      chunkDelayMs: 20,
    });

    // Let the first chunk land, then the user switches to a different,
    // already-open session while A is still streaming (its second chunk
    // hasn't arrived yet).
    await new Promise(resolve => setTimeout(resolve, 10));
    act(() => {
      api.setCurrentSessionId('session-B');
    });

    await streamPromise;

    // The visible `messages` state must reflect session B, not the
    // in-flight session-A stream content.
    expect(api.messages.map(m => m.content).join('')).not.toContain('chunk-A-1');
  });
});
