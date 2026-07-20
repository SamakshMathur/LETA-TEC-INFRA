import { useState, useCallback } from 'react';

const STORAGE_KEY = 'leta.saved.docs';

export interface SavedDoc {
  id: string;
  title: string;
  filename: string;
  size: string;
  category?: string;
}

export function useSavedDocs() {
  const [saved, setSaved] = useState<SavedDoc[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    } catch {
      return [];
    }
  });

  const toggle = useCallback((doc: SavedDoc) => {
    setSaved(prev => {
      const exists = prev.some(d => d.id === doc.id);
      const next = exists ? prev.filter(d => d.id !== doc.id) : [...prev, doc];
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const isSaved = useCallback((id: string) => saved.some(d => d.id === id), [saved]);

  const clear = useCallback(() => {
    setSaved([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { saved, toggle, isSaved, clear };
}
