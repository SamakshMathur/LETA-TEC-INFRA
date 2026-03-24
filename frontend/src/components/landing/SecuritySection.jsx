import { motion } from 'framer-motion';
import React from 'react';
import { Lock, Shield, Server, FileKey } from 'lucide-react';

const SecuritySection = () => {
  return (
    <section className="relative py-32 bg-[#020202] overflow-hidden border-t border-white/5">
      {/* Background Ambience */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(11,115,80,0.03),transparent_70%)] pointer-events-none" />
      
      {/* Encryption Hash Scrolling Background */}
      <div className="absolute inset-0 opacity-5 pointer-events-none overflow-hidden flex flex-col gap-8">
         {[...Array(5)].map((_, i) => (
             <motion.div 
                key={i}
                initial={{ x: -1000 }}
                animate={{ x: 1000 }}
                transition={{ duration: 30 + i * 5, repeat: Infinity, ease: "linear" }}
                className="text-[10px] font-mono text-sentinel-green whitespace-nowrap"
             >
                0x7F4A...3B9C // AES-256 // ENCRYPTED_PACKET // 0x8A1B...4C2D // SECURE_CHANNEL // HANDSHAKE_VERIFIED
             </motion.div>
         ))}
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            {/* Left Column: Brand & Headline */}
            <div className="text-left">
                {/* Animated Vault Icon - Left Aligned */}
                <div className="relative inline-block mb-8">
                    <div className="absolute inset-0 animate-ping opacity-20 rounded-full border border-sentinel-green" />
                    <div className="w-20 h-20 rounded-full bg-[#050A10] border border-sentinel-green/30 flex items-center justify-center relative z-10 shadow-[0_0_40px_rgba(11,115,80,0.1)]">
                        <Shield size={32} className="text-sentinel-green" strokeWidth={1.5} />
                        <motion.div 
                            animate={{ opacity: [0, 1, 0] }}
                            transition={{ duration: 2, repeat: Infinity }}
                            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
                        >
                            <Lock size={16} className="text-white fill-white" />
                        </motion.div>
                    </div>
                </div>

                <h2 className="text-4xl md:text-6xl font-bold text-white mb-6 font-sans tracking-tight leading-tight">
                    Confidentiality First. <br/>
                    <span className="text-gray-500">Always.</span>
                </h2>
                
                <p className="text-gray-400 text-lg leading-relaxed font-light mb-8 font-mono max-w-xl border-l-2 border-sentinel-green/30 pl-6">
                    Sentinel.AI is architected with a profound understanding of the fiduciary obligations carried by tax and legal practitioners.
                </p>

                {/* Security Badges - Aligned Left */}
                <div className="flex flex-wrap gap-3">
                    <div className="px-3 py-1.5 border border-white/10 rounded-sm flex items-center gap-2 bg-white/5 text-[10px] font-mono text-gray-400 uppercase tracking-wider">
                        <Server size={12} className="text-sentinel-green" />
                        <span>ISOLATED_ENV</span>
                    </div>
                    <div className="px-3 py-1.5 border border-white/10 rounded-sm flex items-center gap-2 bg-white/5 text-[10px] font-mono text-gray-400 uppercase tracking-wider">
                        <FileKey size={12} className="text-sentinel-green" />
                        <span>AES_256</span>
                    </div>
                    <div className="px-3 py-1.5 border border-white/10 rounded-sm flex items-center gap-2 bg-white/5 text-[10px] font-mono text-gray-400 uppercase tracking-wider">
                        <Shield size={12} className="text-sentinel-green" />
                        <span>ZERO_LOGS</span>
                    </div>
                </div>
            </div>

            {/* Right Column: Detail Box */}
            <motion.div
                initial={{ opacity: 0, x: 20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                className="bg-[#050A10] border border-white/5 p-10 rounded-sm relative overflow-hidden group hover:border-sentinel-green/20 transition-all duration-300"
            >
                <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-sentinel-green/5 to-transparent rounded-bl-full opacity-0 group-hover:opacity-100 transition-opacity" />
                
                {/* Corner Markers */}
                <div className="absolute top-0 left-0 w-3 h-3 border-t border-l border-white/20 group-hover:border-sentinel-green transition-colors" />
                <div className="absolute bottom-0 right-0 w-3 h-3 border-b border-r border-white/20 group-hover:border-sentinel-green transition-colors" />

                <div className="mb-6 flex items-center gap-2 text-sentinel-green font-mono text-xs uppercase tracking-widest">
                    <div className="w-1.5 h-1.5 rounded-full bg-sentinel-green animate-pulse" />
                     Secure Enclave Active
                </div>

                <p className="text-gray-400 mb-6 relative z-10 leading-8 text-[15px]">
                    Every interaction—be it a query, document upload, or draft generation—remains <span className="text-white font-semibold">strictly confidential</span> and isolated. Your data is never shared, repurposed, or used for model training without explicit consent.
                </p>
                <p className="text-gray-400 relative z-10 leading-8 text-[15px]">
                    All documents are stored effectively in <span className="text-white font-semibold">AES-256 encrypted</span> silos with role-based access controls (RBAC) that meet the highest enterprise security standards.
                </p>
            </motion.div>
        </div>

      </div>
    </section>
  );
};

export default SecuritySection;
