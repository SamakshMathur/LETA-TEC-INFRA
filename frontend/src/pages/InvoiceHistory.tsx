import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Download, Loader2, FileText } from 'lucide-react';
import { AXIOS_INSTANCE as axios } from '../utils/api';
import { BASE_URL } from '../config/api';
import { getAuthHeaders } from '../utils/authHeaders';

const B = {
  accent: '#4FB7C5',
  border: 'rgba(79,183,197,0.14)',
};

export interface InvoiceSummary {
  invoice_number: string;
  payment_id: string;
  plan_name: string;
  amount_paise: number;
  issued_at: string;
}

// Formats a paise amount the same way Payment.tsx and the invoice PDF
// itself do — whole rupees, no decimal noise for round amounts.
export function formatRupees(amountPaise: number): string {
  return `Rs.${(amountPaise / 100).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

export function formatIssuedDate(issuedAt: string): string {
  return new Date(issuedAt).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
  });
}

// Settings page (PR #69) is the only account-management entry point, but
// there was still nowhere to see past payments once the success screen
// was gone — one invoice at a time, on the Payment page itself, only
// right after paying. This is a real history: every invoice a user has
// ever been issued, each independently re-downloadable.
const InvoiceHistory: React.FC = () => {
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState<InvoiceSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    axios.get(`${BASE_URL}/api/payments/invoices`, { headers: getAuthHeaders() })
      .then(res => { if (!cancelled) setInvoices(res.data); })
      .catch(() => { if (!cancelled) setError('Could not load your invoice history. Please try again.'); });
    return () => { cancelled = true; };
  }, []);

  const handleDownload = async (paymentId: string) => {
    if (downloadingId) return;
    setDownloadingId(paymentId);
    setError(null);
    try {
      const res = await fetch(`${BASE_URL}/api/payments/invoice/${paymentId}`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error(`Invoice not available (${res.status})`);
      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="([^"]+)"/);
      const filename = match?.[1] || `LETA-TEC-invoice-${paymentId}.pdf`;

      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      setError('Could not download that invoice right now. Please try again shortly.');
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div
      className="min-h-screen pt-24 pb-16 px-4 sm:px-8"
      style={{ background: 'linear-gradient(160deg, #05070E 0%, #060910 60%, #040611 100%)' }}
    >
      <div className="max-w-2xl mx-auto">
        <motion.button
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3 }}
          onClick={() => navigate('/dashboard')}
          className="flex items-center gap-2 text-xs mb-8 transition-colors"
          style={{ color: '#64748B' }}
          onMouseEnter={e => (e.currentTarget.style.color = B.accent)}
          onMouseLeave={e => (e.currentTarget.style.color = '#64748B')}
        >
          <ArrowLeft size={13} /> Back to dashboard
        </motion.button>

        <h1 className="text-2xl font-bold text-white mb-1" style={{ letterSpacing: '-0.02em' }}>
          Invoice History
        </h1>
        <p className="text-sm mb-8" style={{ color: '#64748B' }}>
          Every invoice issued to your account, newest first
        </p>

        <div className="rounded-2xl overflow-hidden" style={{ background: '#080A10', border: `1px solid ${B.border}` }}>
          {error && (
            <div className="px-6 py-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <p className="text-xs" style={{ color: '#F87171' }}>{error}</p>
            </div>
          )}

          {invoices === null && !error && (
            <div className="px-6 py-10 flex items-center justify-center gap-2" style={{ color: '#64748B' }}>
              <Loader2 size={16} className="animate-spin" />
              <span className="text-sm">Loading invoices…</span>
            </div>
          )}

          {invoices !== null && invoices.length === 0 && (
            <div className="px-6 py-10 flex flex-col items-center gap-2 text-center" style={{ color: '#64748B' }}>
              <FileText size={20} />
              <span className="text-sm">No invoices yet — they'll show up here after your first payment.</span>
            </div>
          )}

          {invoices !== null && invoices.map((inv, i) => (
            <div
              key={inv.payment_id}
              className="px-6 py-4 flex items-center justify-between gap-4"
              style={i < invoices.length - 1 ? { borderBottom: '1px solid rgba(255,255,255,0.05)' } : undefined}
            >
              <div className="min-w-0">
                <p className="text-sm font-semibold truncate" style={{ color: '#F4F7FA' }}>{inv.plan_name}</p>
                <p className="text-[11px] font-mono mt-0.5" style={{ color: '#64748B' }}>
                  {inv.invoice_number} &middot; {formatIssuedDate(inv.issued_at)}
                </p>
              </div>
              <div className="flex items-center gap-4 flex-shrink-0">
                <span className="text-sm font-semibold" style={{ color: '#F4F7FA' }}>{formatRupees(inv.amount_paise)}</span>
                <button
                  onClick={() => handleDownload(inv.payment_id)}
                  disabled={downloadingId === inv.payment_id}
                  aria-label={`Download invoice ${inv.invoice_number}`}
                  className="p-2 rounded-lg transition-colors disabled:opacity-40"
                  style={{ color: B.accent, border: `1px solid ${B.border}` }}
                >
                  {downloadingId === inv.payment_id
                    ? <Loader2 size={14} className="animate-spin" />
                    : <Download size={14} />}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default InvoiceHistory;
