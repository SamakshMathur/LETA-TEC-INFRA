import React from 'react';
import { ShieldCheck, AlertTriangle, AlertOctagon } from 'lucide-react';

const ConfidenceBadge = ({ score }) => {
  let style = { background: 'rgba(71,85,105,0.15)', color: '#94A3B8', border: '1px solid rgba(71,85,105,0.3)' };
  let Icon = ShieldCheck;
  let label = 'Unknown Confidence';

  if (score >= 0.9) {
    style = { background: 'rgba(34,197,94,0.1)', color: '#22C55E', border: '1px solid rgba(34,197,94,0.2)' };
    label = 'High Confidence';
  } else if (score >= 0.7) {
    style = { background: 'rgba(245,158,11,0.1)', color: '#F59E0B', border: '1px solid rgba(245,158,11,0.2)' };
    Icon = AlertTriangle;
    label = 'Medium Confidence';
  } else {
    style = { background: 'rgba(239,68,68,0.1)', color: '#EF4444', border: '1px solid rgba(239,68,68,0.2)' };
    Icon = AlertOctagon;
    label = 'Low Confidence';
  }

  return (
    <div
      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide font-mono"
      style={style}
    >
      <Icon size={13} />
      <span>{label} ({Math.round(score * 100)}%)</span>
    </div>
  );
};

export default ConfidenceBadge;
