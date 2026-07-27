import React from 'react';
import { motion } from 'framer-motion';

const About: React.FC = () => (
  <div className="min-h-screen bg-[#000000]">

    {/* Header */}
    <div className="pt-[140px] pb-20 px-4 sm:px-6 lg:px-8 text-center bg-[#0F1722] border-b border-white/[0.04]">
      <motion.h1
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="font-display font-bold text-4xl md:text-5xl mb-4 tracking-tight text-white uppercase"
      >
        About LETA TEC
      </motion.h1>
      <p className="text-lg font-light max-w-2xl mx-auto text-[#A7B3C2]">
        Advancing statutory intelligence through precision engineering and artificial intelligence.
      </p>
    </div>

    {/* Content */}
    <div className="max-w-4xl mx-auto py-16 px-4 sm:px-6">
      <div className="flex flex-col gap-10">

        <p className="text-base font-light leading-relaxed text-[#A7B3C2]">
          LETA TEC is a premier platform designed for GST professionals, tax consultants, and legal experts.
          We bridge the gap between complex statutory frameworks and actionable intelligence using advanced
          Large Language Models (LLMs).
        </p>

        <div className="rounded-leta p-8 bg-[#0F1722] border border-white/[0.04] shadow-xl">
          <h3 className="font-display font-semibold text-xl mb-3 text-white uppercase tracking-wide">Our Mission</h3>
          <p className="text-base font-light leading-relaxed text-[#A7B3C2]">
            To democratize access to high-level legal reasoning and statutory interpretation, ensuring
            compliance and minimizing litigation risks for businesses across India.
          </p>
        </div>

        <div className="rounded-leta p-8 bg-[#0F1722] border border-white/[0.04] shadow-xl">
          <h3 className="font-display font-semibold text-xl mb-3 text-white uppercase tracking-wide">Core Technology</h3>
          <p className="text-base font-light leading-relaxed text-[#A7B3C2]">
            Powered by{' '}
            <strong className="text-[#4FB7C5] font-semibold">
              LETA (Legal Enterprise Text Agent)
            </strong>
            , our specific model trained on thousands of case laws, circulars, and notifications
            to provide context-aware answers with high confidence.
          </p>
        </div>

      </div>
    </div>
  </div>
);

export default About;
