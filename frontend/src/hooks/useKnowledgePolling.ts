import { useEffect, useRef } from 'react';

export function useKnowledgePolling(
  fetchDocs: () => Promise<void>,
  fetchStatus: () => Promise<void>,
  fetchLogs: () => Promise<void>,
  fetchJobs: () => Promise<void>,
  hasActiveJobs: boolean,
  isLoggedIn: boolean
) {
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!isLoggedIn) return;

    // Initial fetch
    fetchDocs();
    fetchStatus();
    fetchLogs();
    fetchJobs();

    // Poll every 4 seconds
    timerRef.current = setInterval(() => {
      fetchDocs();
      fetchStatus();
      fetchJobs();
      if (hasActiveJobs) {
        fetchLogs();
      }
    }, 4000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [fetchDocs, fetchStatus, fetchLogs, fetchJobs, hasActiveJobs, isLoggedIn]);
}
