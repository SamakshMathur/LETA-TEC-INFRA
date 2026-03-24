import React from 'react';
import { AskLeta } from '../components/leta';
import { FileText, TrendingUp, AlertCircle, Shield, Zap, Activity } from 'lucide-react';

const GST = () => {
  return (
    <div className="min-h-screen bg-[#020202] pb-24 pt-32">
      {/* Cinematic Page Header */}
      <div className="px-6 sm:px-12 lg:px-24 mb-16 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/5 blur-[120px] rounded-full -translate-y-1/2 translate-x-1/2" />
        
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-end justify-between gap-8 relative z-10">
          <div>
            <div className="inline-flex items-center gap-2 py-1 px-3 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-[9px] font-black tracking-[0.2em] text-emerald-400 mb-4 uppercase">
               <Activity size={10} />
               Neural_Hub_Active
            </div>
            <div className="flex items-center gap-4 mb-3">
                 <h1 className="text-4xl md:text-5xl font-black tracking-tighter text-white uppercase italic">
                   GST <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-emerald-600">Intelligence.</span>
                 </h1>
            </div>
            <p className="text-gray-500 font-medium text-xs tracking-widest uppercase flex items-center gap-2">
              <span className="w-8 h-[1px] bg-emerald-500/30" />
              Sovereign Retrieval System v3.0
            </p>
          </div>
          <div className="flex items-center gap-6">
              <div className="flex flex-col items-end">
                <span className="text-[10px] font-black text-gray-500 uppercase tracking-widest mb-1">Live Latency</span>
                <span className="text-emerald-500 text-sm font-mono font-bold">12ms // SYNCED</span>
              </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 lg:px-24 grid grid-cols-1 lg:grid-cols-12 gap-12">
        {/* Main Interface Column (8/12 width) */}
        <div className="lg:col-span-8 bg-glass border-white/5 rounded-3xl p-2 shadow-2xl relative">
          <div className="absolute -inset-[1px] bg-gradient-to-b from-white/10 to-transparent rounded-3xl pointer-events-none" />
           <AskLeta />
        </div>

        {/* Sidebar Info (4/12 width) */}
        <div className="lg:col-span-4 space-y-8">
           {/* Recent Amendments Panel */}
           <div className="bg-glass border-white/5 rounded-3xl overflow-hidden shadow-xl">
              <div className="bg-white/[0.03] px-6 py-5 border-b border-white/5 flex items-center justify-between">
                 <h3 className="font-black text-white text-[10px] tracking-[0.2em] flex items-center gap-3 uppercase">
                   <TrendingUp size={16} className="text-emerald-500" />
                   Recent Synthesis
                 </h3>
                 <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
                 </div>
              </div>
              <ul className="divide-y divide-white/5 font-sans">
                 {[
                   { time: '2 HOURS AGO', title: 'Notification 56/2023: Time limit extension for FY 2018-19' },
                   { time: 'YESTERDAY', title: 'Circular 199: Clarification on ITC regarding warranty replacements' },
                   { time: '2 DAYS AGO', title: 'Rule 88D: Mechanism for dealing with difference in ITC' }
                 ].map((update, i) => (
                   <li key={i} className="p-6 hover:bg-emerald-500/5 cursor-pointer transition-all group border-l-2 border-transparent hover:border-emerald-500">
                      <span className="text-[9px] text-emerald-500 font-black tracking-widest block mb-1 opacity-60 uppercase">{update.time}</span>
                      <p className="text-sm text-gray-400 group-hover:text-white transition-colors leading-relaxed">{update.title}</p>
                   </li>
                 ))}
              </ul>
              <button className="w-full py-4 text-[9px] font-black tracking-[0.3em] uppercase text-gray-500 hover:text-emerald-400 transition-colors border-t border-white/5 bg-white/[0.01]">
                View All Intelligence
              </button>
           </div>

           {/* Compliance Note Panel */}
           <div className="bg-emerald-500/5 border border-emerald-500/20 p-8 rounded-3xl relative overflow-hidden group">
              <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                <AlertCircle size={40} className="text-emerald-400" />
              </div>
              <h3 className="font-black text-emerald-500 flex items-center gap-3 mb-4 text-[10px] tracking-[0.2em] uppercase">
                <Shield size={16} />
                Compliance_Protocol
              </h3>
              <p className="text-xs text-gray-400 leading-relaxed font-sans font-medium">
                 Directives generated are based on statutory provisions of the CGST Act, 2017. 
                 <br/><br/>
                 <span className="text-white/80">&gt;&gt; Synthesis verified against official gazette notifications. Ensure legal review before submission.</span>
              </p>
           </div>
        </div>
      </div>
    </div>
  );
};

export default GST;
