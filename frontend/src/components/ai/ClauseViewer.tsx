import React from 'react';

export const ClauseViewer = ({ clause }: { clause: string }) => {
  return (
    <div className="bg-leta-gray-50 border border-leta-gray-200 rounded-leta p-4">
      <pre className="font-mono text-mono text-leta-gray-900 whitespace-pre-wrap">
        {clause}
      </pre>
    </div>
  );
};
