// Reads the stored JWT and returns an Authorization header object. Shared
// between LetaWorkspace.tsx and LetaResponse.jsx (which needs it too, to
// call the share/unshare endpoints) rather than duplicated — two copies of
// this exact localStorage-reading logic drifting apart is exactly how a
// "works here, silently doesn't work there" auth bug gets introduced later.
export function getAuthHeaders(): Record<string, string> {
  try {
    const stored = localStorage.getItem('pro.auth.session');
    if (!stored) return {};
    const s = JSON.parse(stored);
    const token = s?.tokens?.accessToken;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}
