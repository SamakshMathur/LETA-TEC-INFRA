import React from 'react';
import { DocumentLibrary } from '../components/documents';

// DocumentLibrary itself (search, category rows, circulars/notifications
// year-tabs) was already fully built and wired to real backend endpoints —
// it just had no route pointing at it. MyDocs.tsx's empty state has always
// linked to "/docs" expecting to land here, but that path actually renders
// the unrelated marketing Documentation page — the exact "dead link
// pointing nowhere" class of bug already fixed elsewhere in the footer
// (PR #70) and Settings (PR #69).
const DocumentLibraryPage: React.FC = () => (
  <div className="min-h-screen bg-[#000000] pt-[140px] pb-16 px-4 sm:px-6">
    <div className="max-w-6xl mx-auto">
      <h1 className="font-display font-bold text-3xl md:text-4xl text-white uppercase tracking-tight mb-2">
        Document Library
      </h1>
      <p className="text-sm font-light mb-8" style={{ color: '#A7B3C2' }}>
        Every circular, notification, act, and ruling LETA TEC has indexed — searchable and downloadable.
      </p>
      <DocumentLibrary />
    </div>
  </div>
);

export default DocumentLibraryPage;
