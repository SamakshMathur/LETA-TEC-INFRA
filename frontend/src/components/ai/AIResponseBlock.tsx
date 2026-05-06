import React from 'react';

export const AIResponseBlock = ({ text }: { text: string }) => {
  return (
    <div className="bg-leta-gray-50 border border-leta-gray-100 rounded-leta p-4 shadow-leta">
      <p className="font-body text-body text-leta-gray-900">{text}</p>
    </div>
  );
};
