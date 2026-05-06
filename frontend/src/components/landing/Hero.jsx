import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Heading } from '../typography/Heading';
import { Button } from '../ui/Button';
import { AIResponseBlock } from '../ai/AIResponseBlock';

const Hero = () => {
  return (
    <div className="relative min-h-screen flex items-center justify-center bg-leta-white pt-24 pb-16 overflow-hidden">
      
      {/* Subtle Background Grid */}
      <div 
        className="absolute inset-0 z-0 opacity-[0.03]"
        style={{
          backgroundImage: 'linear-gradient(to right, #111827 1px, transparent 1px), linear-gradient(to bottom, #111827 1px, transparent 1px)',
          backgroundSize: '40px 40px'
        }}
      />

      <div className="relative z-10 max-w-7xl mx-auto px-6 w-full">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
          
          {/* Left Side: Copy & CTA */}
          <motion.div
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 mb-6 rounded-full bg-leta-gray-50 border border-leta-gray-200">
              <span className="w-2 h-2 rounded-full bg-leta-primary animate-pulse" />
              <span className="text-xs font-semibold text-leta-gray-700 uppercase tracking-wider">
                System Status: Active
              </span>
            </div>

            <Heading level="h1" className="text-leta-gray-900 mb-6 tracking-tight">
              Legal Intelligence, Redefined
            </Heading>
            
            <p className="font-body text-bodyLg text-leta-gray-500 mb-10 max-w-lg leading-relaxed">
              Engineering the future of GST Compliance with high-fidelity retrieval and sovereign intelligence. Built exclusively for professionals.
            </p>
            
            <div className="flex flex-wrap items-center gap-4">
              <Link to="/gst">
                <Button variant="primary">
                  Initialize Titan
                </Button>
              </Link>
              <Link to="/docs">
                <Button variant="ghost">
                  View Documentation →
                </Button>
              </Link>
            </div>
          </motion.div>

          {/* Right Side: Product Preview */}
          <motion.div
            initial={{ opacity: 0, x: 30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
            className="relative"
          >
            {/* Decorative backing */}
            <div className="absolute -inset-4 bg-gradient-to-tr from-leta-gray-50 to-leta-white border border-leta-gray-100 rounded-2xl -z-10 shadow-sm" />
            
            {/* Mock UI */}
            <div className="bg-leta-white border border-leta-gray-200 rounded-2xl shadow-elevated p-6 flex flex-col gap-6 relative overflow-hidden">
              
              <div className="flex items-center justify-between border-b border-leta-gray-100 pb-4">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-leta-primary/10 flex items-center justify-center">
                    <span className="text-leta-primary font-bold text-sm">AI</span>
                  </div>
                  <span className="font-heading font-semibold text-leta-gray-900">Query Analysis</span>
                </div>
                <span className="text-xs font-mono text-leta-gray-400 bg-leta-gray-50 px-2 py-1 rounded-md">
                  v3.0_STABLE
                </span>
              </div>

              <div className="bg-leta-gray-50 rounded-lg p-4 border border-leta-gray-200">
                <p className="font-mono text-sm text-leta-gray-700">
                  &gt; Input: Section 16(4) of CGST Act conditions
                </p>
              </div>

              <AIResponseBlock text="Input tax credit must be claimed before the 30th of November following the end of the financial year to which the invoice pertains, or furnishing of the relevant annual return, whichever is earlier." />
              
            </div>
          </motion.div>
          
        </div>
      </div>
    </div>
  );
};

export default Hero;
