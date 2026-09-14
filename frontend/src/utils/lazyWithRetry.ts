import { lazy, type ComponentType } from 'react';

// Every route is React.lazy()-loaded — its JS chunk is fetched only when
// that route is first visited, and the browser resolves the chunk's URL
// against the *currently loaded* index.html, which pins exact content
// hashes ("LetaWorkspace-CYmpIWUP.js"). The moment a new deploy replaces
// those files, any tab that was already open (or is running from a cached
// index.html) is still holding the OLD hashes — the next lazy import for a
// route it hasn't visited yet 404s outright, since that exact file no
// longer exists on the server. Vite's import() rejects with a plain
// TypeError ("Failed to fetch dynamically imported module: ..."), which
// React.lazy has no built-in recovery for — it just throws past the
// nearest ErrorBoundary and dead-ends on "Something went wrong", even
// though the fix is trivial: reload, which fetches the current index.html
// referencing the current hashes.
//
// This happens routinely here — deploys ship multiple times an hour some
// days — so it isn't a one-off; every `lazy()` call in routes/index.tsx
// goes through this wrapper instead of React's directly.
function isChunkLoadError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return (
    /Failed to fetch dynamically imported module/i.test(message) ||
    /Importing a module script failed/i.test(message) || // Safari's wording
    /error loading dynamically imported module/i.test(message) // Firefox's wording
  );
}

const RELOAD_GUARD_KEY = 'leta.chunkLoadReloadAttempted';

export function lazyWithRetry<T extends { default: ComponentType<unknown> }>(
  factory: () => Promise<T>
) {
  return lazy(async () => {
    try {
      const mod = await factory();
      // A later stale-chunk event (e.g. hours into the same tab, after
      // another deploy) deserves its own one-shot reload too — only guard
      // against reloading twice for the SAME failed fetch.
      sessionStorage.removeItem(RELOAD_GUARD_KEY);
      return mod;
    } catch (error) {
      if (isChunkLoadError(error) && !sessionStorage.getItem(RELOAD_GUARD_KEY)) {
        sessionStorage.setItem(RELOAD_GUARD_KEY, '1');
        window.location.reload();
        // The reload is already navigating away — resolve to nothing
        // rather than let React.lazy's real rejection race it to the
        // error boundary and flash "Something went wrong" first.
        return new Promise<T>(() => {});
      }
      // A second consecutive failure, or a genuinely different error
      // (not staleness — an actually broken deploy, a network outage) —
      // don't reload-loop the user forever. Let it surface to the
      // ErrorBoundary as before.
      throw error;
    }
  });
}
