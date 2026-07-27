import { motion } from 'framer-motion';
import React from 'react';
import { TrendingUp, Shield, Users, Clock } from 'lucide-react';

const cards = [
  { icon: TrendingUp, title: 'Accelerate Compliance',  desc: 'Reduce research time by 80% with instant statutory cross-referencing.' },
  { icon: Shield,     title: 'Risk Mitigation',        desc: 'Proactively identify non-compliance risks in vendor ITC claims.' },
  { icon: Users,      title: 'Client Advisory',        desc: 'Generate professional, reasoned opinions for client queries in seconds.' },
  { icon: Clock,      title: 'Real-time Updates',      desc: 'Always synchronized with the latest Notifications and Circulars.' },
];

const PromoCards = () => {
  return (
    <section className="py-[140px] relative overflow-hidden border-t border-white/[0.05]">

      {/* Ambient glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] pointer-events-none bg-[radial-gradient(ellipse,rgba(103,232,249,0.02)_0%,transparent_70%)] blur-[60px]" />

      <div className="w-full px-10 lg:px-20 relative z-10">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-left mb-12 pb-6 border-b border-white/[0.05]"
        >
          <span className="font-mono text-xs tracking-[0.2em] uppercase mb-2 block text-[#67E8F9]">
            // SYSTEM_CAPABILITIES
          </span>
          <h2 className="text-3xl md:text-4xl font-bold text-[#F5F7FA] font-display tracking-tight uppercase">
            Why Professionals Choose LETA TEC
          </h2>
        </motion.div>

        {/* Cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {cards.map((card, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, scale: 0.95 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: idx * 0.08 }}
              className="p-6 rounded-leta relative overflow-hidden cursor-default group transition-all duration-300 bg-[#151922] border border-white/[0.06] hover:border-[#67E8F9]/18 hover:-translate-y-0.5 shadow-2xl"
            >
              {/* Corner markers */}
              <div className="absolute top-0 right-0 w-2 h-2 border-t border-r border-[#67E8F9]/10 group-hover:border-[#67E8F9]/30 transition-colors duration-300" />
              <div className="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-[#67E8F9]/10 group-hover:border-[#67E8F9]/30 transition-colors duration-300" />

              {/* Icon */}
              <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-6 transition-all duration-300 bg-white/[0.02] border border-white/[0.05] text-[#67E8F9] group-hover:scale-105">
                <card.icon size={22} strokeWidth={1.5} />
              </div>

              <h3 className="text-sm font-bold text-white mb-3 font-mono uppercase tracking-wider">
                {card.title}
              </h3>
              <p className="text-sm font-mono leading-relaxed text-[#A1AAB8]">
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
