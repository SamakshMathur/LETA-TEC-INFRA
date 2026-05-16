import React from 'react';
import { AskLeta } from '../components/leta';
import { TrendingUp, AlertCircle, Shield, Activity } from 'lucide-react';

const GST: React.FC = () => {
  return (
    <div className="min-h-screen pb-24 pt-[140px] bg-[#000000]">

      {/* ── Page Header ──────────────────────────────────────────────────────── */}
      <div className="px-6 sm:px-12 lg:px-24 mb-12 relative overflow-hidden">
        {/* Ambient glow */}
        <div className="absolute top-0 right-0 w-96 h-64 rounded-full pointer-events-none bg-[radial-gradient(circle,rgba(103,232,249,0.02)_0%,transparent_70%)] blur-[80px]" />

        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-end justify-between gap-8 relative z-10">
          <div>
            {/* Status badge */}
            <div className="inline-flex items-center gap-2 py-1.5 px-3.5 rounded-full mb-5 border border-white/[0.06] bg-white/[0.02]">
              <Activity size={10} className="text-[#67E8F9]" />
              <span className="text-[9px] font-black tracking-[0.2em] uppercase font-mono text-[#67E8F9]">
                Statutory_Database_Active
              </span>
            </div>

            <h1 className="text-4xl md:text-5xl font-bold tracking-tight text-[#F5F7FA] uppercase font-display mb-3">
              GST Intelligence
            </h1>

            <p className="text-xs tracking-widest uppercase font-mono flex items-center gap-2 text-[#A1AAB8]/40">
              <span className="w-8 h-[1px] bg-white/[0.05]" />
              Professional Search & Retrieval Engine v4.0
            </p>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex flex-col items-end">
              <span className="text-[10px] font-black uppercase tracking-widest mb-1 font-mono text-[#A1AAB8]/40">
                Live Latency
              </span>
              <span className="text-sm font-mono font-bold text-emerald-500">
                12ms // SYNCED
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Main Grid ────────────────────────────────────────────────────────── */}
      <div className="max-w-7xl mx-auto px-6 lg:px-24 grid grid-cols-1 lg:grid-cols-12 gap-10">

        {/* AskLeta Console — 8/12 */}
        <div className="lg:col-span-8">
          <AskLeta />
        </div>

        {/* Sidebar — 4/12 */}
        <div className="lg:col-span-4 space-y-6">

          {/* Recent Synthesis Panel */}
          <div className="rounded-leta overflow-hidden bg-[#000000] border border-white/[0.06] shadow-2xl">
            <div className="px-5 py-4 flex items-center justify-between border-b border-white/[0.06]">
              <h3 className="font-black text-[10px] tracking-[0.2em] flex items-center gap-2 uppercase font-mono text-[#F5F7FA]">
                <TrendingUp size={14} className="text-[#67E8F9]" />
                Recent Synthesis
              </h3>
              <div className="flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              </div>
            </div>

            <ul>
              {[
                { time: '2 HOURS AGO', title: 'Notification 56/2023: Time limit extension for FY 2018-19' },
                { time: 'YESTERDAY',   title: 'Circular 199: Clarification on ITC regarding warranty replacements' },
                { time: '2 DAYS AGO', title: 'Rule 88D: Mechanism for dealing with difference in ITC' },
              ].map((update, i) => (
                <li
                  key={i}
                  className="p-5 cursor-pointer transition-all border-l-2 border-transparent hover:border-[#67E8F9] hover:bg-white/[0.02] border-b border-white/[0.06] last:border-b-0"
                >
                  <span className="text-[9px] font-black tracking-widest block mb-1 uppercase font-mono text-[#67E8F9]/60">
                    {update.time}
                  </span>
                  <p className="text-sm leading-relaxed text-[#A1AAB8]">
                    {update.title}
                  </p>
                </li>
              ))}
            </ul>

            <button className="w-full py-4 text-[9px] font-black tracking-[0.3em] uppercase font-mono text-[#A1AAB8]/40 hover:text-[#67E8F9] border-t border-white/[0.06] transition-colors bg-transparent">
              View All Intelligence
            </button>
          </div>

          {/* Compliance Protocol Panel */}
          <div className="p-6 rounded-leta relative overflow-hidden group border border-white/[0.06] bg-[#000000] shadow-2xl">
            <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
              <AlertCircle size={48} className="text-[#67E8F9]" />
            </div>

            <h3 className="font-black flex items-center gap-2 mb-4 text-[10px] tracking-[0.2em] uppercase font-mono text-[#67E8F9]">
              <Shield size={14} />
              Compliance_Protocol
            </h3>

            <p className="text-xs leading-relaxed font-mono text-[#A1AAB8]">
              Directives generated are based on statutory provisions of the CGST Act, 2017.
              <br /><br />
              <span className="text-[#F5F7FA]/80">
                &gt;&gt; Synthesis verified against official gazette notifications. Ensure legal review before submission.
              </span>
            </p>
          </div>

        </div>
      </div>
    </div>
  );
};

export default GST;
