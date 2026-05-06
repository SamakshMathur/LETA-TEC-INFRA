import React from 'react';
import { motion } from 'framer-motion';

const About: React.FC = () => (
  <div className="min-h-screen" style={{ backgroundColor: 'var(--surface)' }}>

    {/* Header */}
    <div className="pt-32 pb-20 px-4 sm:px-6 lg:px-8 text-center" style={{ backgroundColor: 'var(--surface-container-low)' }}>
      <motion.h1
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="font-display font-bold text-4xl md:text-5xl mb-4 tracking-tight"
        style={{ color: '#e5e2e1' }}
      >
        About Sentinel.AI
      </motion.h1>
      <p className="text-lg font-light max-w-2xl mx-auto" style={{ color: '#9a9a9a' }}>
        Advancing statutory intelligence through precision engineering and artificial intelligence.
      </p>
    </div>

    {/* Content */}
    <div className="max-w-4xl mx-auto py-16 px-4 sm:px-6">
      <div className="flex flex-col gap-10">

        <p className="text-base font-light leading-relaxed" style={{ color: '#9a9a9a' }}>
          Sentinel.AI is a premier platform designed for GST professionals, tax consultants, and legal experts.
          We bridge the gap between complex statutory frameworks and actionable intelligence using advanced
          Large Language Models (LLMs).
        </p>

        <div
          className="rounded-leta p-6"
          style={{ backgroundColor: 'var(--surface-container-high)' }}
        >
          <h3 className="font-semibold text-lg mb-3" style={{ color: '#e5e2e1' }}>Our Mission</h3>
          <p className="text-base font-light leading-relaxed" style={{ color: '#9a9a9a' }}>
            To democratize access to high-level legal reasoning and statutory interpretation, ensuring
            compliance and minimizing litigation risks for businesses across India.
          </p>
        </div>

        <div
          className="rounded-leta p-6"
          style={{ backgroundColor: 'var(--surface-container-high)' }}
        >
          <h3 className="font-semibold text-lg mb-3" style={{ color: '#e5e2e1' }}>Core Technology</h3>
          <p className="text-base font-light leading-relaxed" style={{ color: '#9a9a9a' }}>
            Powered by{' '}
            <strong style={{ color: '#4F46E5', fontWeight: 600 }}>
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
