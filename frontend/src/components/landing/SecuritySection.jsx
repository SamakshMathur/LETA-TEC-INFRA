import { motion } from 'framer-motion';
import React from 'react';
import { Lock, Shield, Server, FileKey } from 'lucide-react';

const SecuritySection = () => {
  return (
    <section className="relative py-[140px] bg-[#000000] overflow-hidden border-t border-white/[0.05]">

      {/* Scrolling encryption hash bg */}
      <div className="absolute inset-0 opacity-[0.015] pointer-events-none overflow-hidden flex flex-col gap-8 justify-center">
        {[...Array(5)].map((_, i) => (
          <motion.div
            key={i}
            initial={{ x: -1200 }}
            animate={{ x: 1200 }}
            transition={{ duration: 30 + i * 5, repeat: Infinity, ease: 'linear' }}
            className="text-[10px] font-mono whitespace-nowrap text-white"
          >
            0x7F4A...3B9C // AES-256 // ENCRYPTED_PACKET // 0x8A1B...4C2D // SECURE_CHANNEL // HANDSHAKE_VERIFIED
          </motion.div>
        ))}
      </div>

      {/* Ambient glow */}
      <div className="absolute inset-0 pointer-events-none bg-[radial-gradient(ellipse_at_30%_50%,rgba(79,183,197,0.01)_0%,transparent_60%)]" />

      <div className="w-full px-10 lg:px-20 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

          {/* Left: Headline */}
          <div className="text-left">
            {/* Animated vault icon */}
            <div className="relative inline-block mb-8">
              <div className="absolute inset-0 animate-pulse opacity-20 rounded-full border border-white/[0.05]" />
              <div className="w-20 h-20 rounded-full flex items-center justify-center relative z-10 border border-white/[0.06] bg-white/[0.01]">
                <Shield size={30} className="text-[#4FB7C5]" strokeWidth={1.5} />
                <motion.div
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 3, repeat: Infinity }}
                  className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
                >
                  <Lock size={14} className="text-[#4FB7C5]" />
                </motion.div>
              </div>
            </div>

            <h2 className="text-4xl md:text-6xl font-bold text-[#F4F7FA] mb-6 font-display tracking-tight leading-tight uppercase">
              Confidentiality First. <br />
              <span className="text-[#6C7A99]">Always.</span>
            </h2>

            <p className="text-lg leading-relaxed font-light mb-8 font-sans max-w-xl pl-6 border-l-2 border-[#4FB7C5]/30 text-[#A7B3C2]">
              LETA Titan is architected with a profound understanding of the fiduciary
              obligations carried by tax and legal practitioners.
            </p>

            {/* Security badges */}
            <div className="flex flex-wrap gap-3">
              {[
                { Icon: Server,  label: 'ISOLATED_ENV' },
                { Icon: FileKey, label: 'AES_256' },
                { Icon: Shield,  label: 'ZERO_LOGS' },
              ].map(({ Icon, label }) => (
                <div
                  key={label}
                  className="px-3 py-1.5 rounded-lg flex items-center gap-2 text-[10px] font-sans font-semibold uppercase tracking-wider border border-white/[0.06] bg-[#0F1722] text-[#4FB7C5]"
                >
                  <Icon size={11} />
                  <span>{label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right: Detail box */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            className="relative overflow-hidden group transition-all duration-300 rounded-leta p-10 bg-[#0F1722] border border-white/[0.04] shadow-2xl hover:border-[#4FB7C5]/18"
          >
            {/* Corner markers */}
            <div className="absolute top-0 left-0 w-3 h-3 border-t border-l border-[#4FB7C5]/20 group-hover:border-[#4FB7C5]/40 transition-colors duration-300" />
            <div className="absolute bottom-0 right-0 w-3 h-3 border-b border-r border-[#4FB7C5]/20 group-hover:border-[#4FB7C5]/40 transition-colors duration-300" />

            <div className="mb-6 flex items-center gap-2 font-sans text-xs font-semibold uppercase tracking-widest text-[#4FB7C5]">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Secure Enclave Active
            </div>

            <p className="mb-6 relative z-10 leading-8 text-[15px] text-[#A7B3C2]">
              Every interaction—be it a query, document upload, or draft generation—remains{' '}
              <span className="font-semibold text-[#4FB7C5]">strictly confidential</span>{' '}
              and isolated. Your data is never shared, repurposed, or used for model training without explicit consent.
            </p>
            <p className="relative z-10 leading-8 text-[15px] text-[#A7B3C2]">
              All documents are stored effectively in{' '}
              <span className="font-semibold text-[#4FB7C5]">AES-256 encrypted</span>{' '}
              silos with role-based access controls (RBAC) that meet the highest enterprise security standards.
            </p>
          </motion.div>

        </div>
      </div>
    </section>
  );
};

export default SecuritySection;
