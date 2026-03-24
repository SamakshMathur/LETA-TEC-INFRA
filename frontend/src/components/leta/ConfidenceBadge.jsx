import React from 'react';
import { ShieldCheck, AlertTriangle, AlertOctagon } from 'lucide-react';

// Confidence levels mapping
// > 90% -> High (Green)
// 70-90% -> Medium (Yellow/Orange)
// < 70% -> Low (Red)

const ConfidenceBadge = ({ score }) => {
  let colorClass = "bg-gray-100 text-gray-600 border-gray-200";
  let icon = ShieldCheck;
  let label = "Unknown Confidence";

  if (score >= 0.9) {
    colorClass = "bg-sentinel-green/10 text-sentinel-green border-sentinel-green/20";
    label = "High Confidence";
  } else if (score >= 0.7) {
    colorClass = "bg-yellow-50 text-yellow-700 border-yellow-200";
    icon = AlertTriangle;
    label = "Medium Confidence";
  } else {
    colorClass = "bg-red-50 text-red-700 border-red-200";
    icon = AlertOctagon;
    label = "Low Confidence";
  }

  const Icon = icon;

  return (
    <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-semibold uppercase tracking-wide ${colorClass}`}>
      <Icon size={14} />
      <span>{label} ({Math.round(score * 100)}%)</span>
    </div>
  );
};

export default ConfidenceBadge;
