import React from 'react';
import { Database, Folder, Shield, ArrowRight, ChevronRight, HelpCircle, FileText } from 'lucide-react';

const SimulatedWorkspace = () => {
  return (
    <section className="py-[80px] bg-[#070B11] relative overflow-hidden border-b border-white/[0.03]">
      <div className="max-w-[1600px] mx-auto px-10 lg:px-20 relative z-10">
        
        {/* Section Header */}
        <div className="mb-16 text-center max-w-3xl mx-auto">
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.15em] text-[#4FB7C5] mb-3">
            Realist Operations Sandbox
          </p>
          <h2 className="font-display font-bold text-3xl md:text-5xl text-white uppercase tracking-tight">
            Operational Intelligence Workspace
          </h2>
          <p className="font-body text-[#A7B3C2] text-sm md:text-base mt-4 leading-relaxed font-light">
            A realistic preview of the production-ready LETA operational workspace used by legal, advisory, and compliance teams.
          </p>
        </div>

        {/* Workspace Shell */}
        <div className="rounded-leta border border-white/[0.05] bg-[#0F1722] shadow-[0_10px_50px_rgba(0,0,0,0.18)] overflow-hidden">
          
          {/* Top Bar */}
          <div className="px-6 py-4 bg-white/[0.01] border-b border-white/[0.04] flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="flex gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500/20" />
                <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/20" />
                <span className="w-2.5 h-2.5 rounded-full bg-green-500/20" />
              </div>
              <span className="font-sans text-[11px] font-semibold text-[#6C7A99] ml-4 tracking-wider uppercase">
                LETA Interactive Workspace
              </span>
            </div>
            <div className="flex items-center gap-4">
              <span className="font-sans text-[10px] text-emerald-400 flex items-center gap-1.5 bg-emerald-400/5 px-2.5 py-1 rounded border border-emerald-400/10 font-semibold tracking-wider">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                PORT_CONNECTED
              </span>
            </div>
          </div>

          {/* Core Shell Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[580px] text-xs">
            
            {/* LEFT BAR: Navigation & Modules */}
            <div className="lg:col-span-3 border-r border-white/[0.04] p-6 space-y-6 bg-white/[0.005]">
              <div className="space-y-2">
                <p className="font-sans text-[10px] font-semibold uppercase text-[#6C7A99] tracking-wider mb-3">
                  STATUTORY FILESYSTEM
                </p>
                <div className="flex items-center gap-2.5 p-2 rounded-lg text-[#4FB7C5] bg-[#4FB7C5]/5 font-sans font-medium">
                  <Folder size={14} />
                  <span>CGST_Act_2017</span>
                </div>
                <div className="flex items-center gap-2.5 p-2 rounded-lg text-[#A7B3C2] hover:text-white transition-colors cursor-pointer font-sans pl-6">
                  <FileText size={14} />
                  <span>Section_17_5_Exemptions</span>
                </div>
                <div className="flex items-center gap-2.5 p-2 rounded-lg text-[#A7B3C2] hover:text-white transition-colors cursor-pointer font-sans pl-6">
                  <FileText size={14} />
                  <span>Circular_177_09_2022</span>
                </div>
                <div className="flex items-center gap-2.5 p-2 rounded-lg text-[#A7B3C2] hover:text-white transition-colors cursor-pointer font-sans">
                  <Folder size={14} />
                  <span>FEMA_Regulations</span>
                </div>
                <div className="flex items-center gap-2.5 p-2 rounded-lg text-[#A7B3C2] hover:text-white transition-colors cursor-pointer font-sans">
                  <Folder size={14} />
                  <span>Income_Tax_Directives</span>
                </div>
              </div>

              <div className="pt-6 border-t border-white/[0.04] space-y-2">
                <p className="font-sans text-[10px] font-semibold uppercase text-[#6C7A99] tracking-wider mb-3">
                  SYSTEM TELEMETRY
                </p>
                <div className="flex justify-between font-sans text-[11px] text-[#6C7A99]">
                  <span>Active Query Nodes</span>
                  <span className="text-[#4FB7C5] font-semibold">1,243</span>
                </div>
                <div className="flex justify-between font-sans text-[11px] text-[#6C7A99]">
                  <span>Avg Latency Target</span>
                  <span className="text-white font-semibold">2.3s</span>
                </div>
              </div>
            </div>

            {/* CENTER BAR: Legal Query Console */}
            <div className="lg:col-span-5 p-8 flex flex-col justify-between space-y-8">
              <div className="space-y-6">
                <div className="flex items-center gap-2 font-sans text-[10px] font-semibold uppercase text-[#6C7A99]">
                  <Database size={12} className="text-[#4FB7C5]" />
                  <span>Statutory_Query_Input</span>
                </div>

                <div className="space-y-3">
                  <label className="font-sans text-[10px] font-semibold uppercase text-[#6C7A99] tracking-wide">
                    Interrogate Compliance Database
                  </label>
                  <div className="p-4 rounded-xl bg-white/[0.01] border border-white/[0.04] font-body text-[#A7B3C2] text-xs leading-relaxed">
                    &gt; Is input tax credit (ITC) available for the construction of a pipeline under works contract if used strictly for direct commercial output?
                  </div>
                </div>

                <div className="flex flex-wrap gap-2.5">
                  <span className="px-2.5 py-1 rounded bg-[#4FB7C5]/5 border border-[#4FB7C5]/10 text-[#4FB7C5] font-sans text-[10px] uppercase font-bold">
                    CGST_Act
                  </span>
                  <span className="px-2.5 py-1 rounded bg-white/[0.01] border border-white/[0.05] text-[#A7B3C2] font-mono text-[10px] uppercase">
                    Section_17_5_c
                  </span>
                  <span className="px-2.5 py-1 rounded bg-white/[0.01] border border-white/[0.05] text-[#A7B3C2] font-mono text-[10px] uppercase">
                    Circular_172
                  </span>
                </div>
              </div>

              <div className="pt-6 border-t border-white/[0.04] flex items-center justify-between">
                <div className="flex items-center gap-2 text-[#6C7A99] font-sans text-[10px]">
                  <Shield size={12} className="text-[#4FB7C5]" />
                  <span>Encrypted Sandbox Environment</span>
                </div>
                <button className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-black font-semibold font-sans text-[12px] bg-[#4FB7C5] hover:bg-[#3EA6B4] transition-all">
                  Execute Query <ArrowRight size={12} />
                </button>
              </div>
            </div>

            {/* RIGHT BAR: AI Response & Citation Breakdown */}
            <div className="lg:col-span-4 border-l border-white/[0.04] p-8 flex flex-col justify-between bg-white/[0.005]">
              <div className="space-y-6">
                <div className="flex items-center justify-between font-sans text-[10px] font-semibold uppercase text-[#6C7A99] border-b border-white/[0.03] pb-4">
                  <span>Structured_Reasoning_Output</span>
                  <span className="text-[#4FB7C5] font-bold">CONFIDENCE 94.2%</span>
                </div>

                <div className="space-y-4 font-body text-[#A7B3C2]">
                  <div className="p-4 rounded-xl bg-emerald-500/[0.01] border border-emerald-500/15 space-y-2">
                    <p className="text-emerald-400 font-bold text-xs uppercase tracking-wide">
                      ✔ ADVISORY SUMMARY
                    </p>
                    <p className="text-xs leading-relaxed font-light">
                      ITC is generally blocked under Section 17(5)(c) for construction except where the pipeline falls under the definition of "plant and machinery".
                    </p>
                  </div>

                  <div className="space-y-3 pt-2">
                    <p className="text-[#6C7A99] text-[9px] uppercase tracking-wider">Citations Found (3)</p>
                    <div className="p-3 rounded-lg bg-white/[0.01] border border-white/[0.04] flex items-center justify-between cursor-pointer hover:bg-white/[0.02]">
                      <span className="font-semibold text-white">CGST Section 17(5)(c)</span>
                      <ChevronRight size={12} className="text-[#6C7A99]" />
                    </div>
                    <div className="p-3 rounded-lg bg-white/[0.01] border border-white/[0.04] flex items-center justify-between cursor-pointer hover:bg-white/[0.02]">
                      <span className="font-semibold text-white">Circular No. 177/09/2022</span>
                      <ChevronRight size={12} className="text-[#6C7A99]" />
                    </div>
                  </div>
                </div>
              </div>

              <div className="pt-6 border-t border-white/[0.03] flex items-center justify-between font-sans text-[11px] text-[#6C7A99]">
                <span className="flex items-center gap-1">
                  <HelpCircle size={10} />
                  Citation fidelity
                </span>
                <span className="text-[#4FB7C5] font-semibold">100% EXPLICIT MAP</span>
              </div>
            </div>

          </div>

        </div>

      </div>
    </section>
  );
};

export default SimulatedWorkspace;
