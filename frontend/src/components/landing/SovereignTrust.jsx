import React from 'react';
import { ShieldAlert, Server, Layers, Key } from 'lucide-react';

const TRUST_METRICS = [
  {
    icon: Layers,
    value: '14M+',
    label: 'Statutory References Indexed',
    desc: 'Deep indexing of Central & State GST, Income Tax codes, notifications, circular guidelines, and historic tribunal orders.',
  },
  {
    icon: Server,
    value: '2.3s',
    label: 'Avg Advisory Generation',
    desc: 'High-performance statutory retrieval and reasoning pipeline producing citations and compliance advisory in seconds.',
  },
  {
    icon: ShieldAlert,
    value: '99.2%',
    label: 'Statutory Mapping Accuracy',
    desc: 'Rigorous cross-referencing logic filtering contradictions between historic case laws and active legal exceptions.',
  },
  {
    icon: Key,
    value: '256-Bit',
    label: 'Enterprise Ingestion Encryption',
    desc: 'Sovereign data encapsulation ensuring secure workspace queries and private corporate document storage.',
  },
];

const SovereignTrust = () => {
  return (
    <section className="py-[80px] bg-[#070B11] relative overflow-hidden border-t border-white/[0.03]">
      <div className="max-w-[1600px] mx-auto px-10 lg:px-20 relative z-10">
        
        {/* Section Header */}
        <div className="mb-20 text-center lg:text-left">
          <p className="font-sans text-[11px] font-semibold uppercase tracking-[0.15em] text-[#4FB7C5] mb-3">
            Security &amp; Integrity Infrastructure
          </p>
          <h2 className="font-display font-bold text-3xl md:text-5xl text-white uppercase tracking-tight">
            Sovereign Trust Layer
          </h2>
          <p className="font-body text-[#A7B3C2] text-base md:text-lg max-w-xl mt-4 leading-relaxed font-light">
            Concrete compliance performance metrics, enterprise-grade encryption, and real-time statutory coverage statistics.
          </p>
        </div>

        {/* Metrics Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {TRUST_METRICS.map((item, index) => {
            const IconComponent = item.icon;
            return (
              <div
                key={index}
                className="p-8 rounded-leta bg-[#0F1722] border border-white/[0.04] flex flex-col justify-between hover:border-[#4FB7C5]/15 transition-all duration-300 min-h-[280px]"
              >
                <div>
                  {/* Icon Badge */}
                  <div className="w-10 h-10 rounded-xl bg-white/[0.01] border border-white/[0.04] flex items-center justify-center text-[#4FB7C5] mb-6">
                    <IconComponent size={18} />
                  </div>

                  {/* Value */}
                  <p className="font-display font-bold text-4xl lg:text-5xl text-white tracking-tight mb-2">
                    {item.value}
                  </p>

                  {/* Label */}
                  <h3 className="font-sans text-[11px] font-semibold uppercase tracking-wider text-[#4FB7C5] mb-3">
                    {item.label}
                  </h3>
                </div>

                {/* Description */}
                <p className="font-body text-[12px] font-light leading-relaxed text-[#6C7A99]">
                  {item.desc}
                </p>
              </div>
            );
          })}
        </div>

      </div>
    </section>
  );
};

export default SovereignTrust;
