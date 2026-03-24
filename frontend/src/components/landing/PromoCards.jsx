import { motion } from 'framer-motion';
import React from 'react';
import { TrendingUp, Shield, Users, Clock } from 'lucide-react';

const cards = [
  {
    icon: TrendingUp,
    title: "Accelerate Compliance",
    desc: "Reduce research time by 80% with instant statutory cross-referencing."
  },
  {
    icon: Shield,
    title: "Risk Mitigation",
    desc: "Proactively identify non-compliance risks in vendor ITC claims."
  },
  {
    icon: Users,
    title: "Client Advisory",
    desc: "Generate professional, reasoned opinions for client queries in seconds."
  },
  {
    icon: Clock,
    title: "Real-time Updates",
    desc: "Always synchronized with the latest Notifications and Circulars."
  }
];

const PromoCards = () => {
  return (
    <section className="py-24 relative overflow-hidden bg-[#020202] border-t border-white/5">
        
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
        <motion.div 
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-left mb-12 border-b border-white/10 pb-6"
        >
          <span className="text-sentinel-green font-mono text-xs tracking-[0.2em] uppercase mb-2 block">
            // SYSTEM_CAPABILITIES
          </span>
          <h2 className="text-3xl md:text-4xl font-bold text-white font-sans tracking-tight">
            Why Professionals Choose <span className="text-gray-500">Sentinel.AI</span>
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {cards.map((card, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: idx * 0.1 }}
              className="bg-[#050A10] p-6 border border-white/5 hover:border-sentinel-green/40 transition-all duration-300 group cursor-default relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 w-2 h-2 border-t border-r border-white/20 group-hover:border-sentinel-green transition-colors" />
              <div className="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-white/20 group-hover:border-sentinel-green transition-colors" />

              <div className="w-12 h-12 rounded-sm bg-sentinel-blue/5 border border-sentinel-blue/10 flex items-center justify-center text-sentinel-blue mb-6 group-hover:bg-sentinel-green/10 group-hover:text-sentinel-green group-hover:border-sentinel-green/30 transition-all duration-300">
                <card.icon size={24} strokeWidth={1.5} />
              </div>
              <h3 className="text-lg font-bold text-white mb-3 font-mono uppercase tracking-wider group-hover:text-sentinel-green transition-colors">
                {card.title}
              </h3>
              <p className="text-sm text-gray-500 leading-relaxed font-mono">
                {card.desc}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default PromoCards;
