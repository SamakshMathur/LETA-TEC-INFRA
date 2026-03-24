import React, { useEffect, useState, useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { Brain, ShieldCheck, Zap } from 'lucide-react';
import { NeuralBackground } from '../effects';

const ScifiText = ({ text, className }) => {
  const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789@#$%&*';
  const [displayText, setDisplayText] = useState('');
  const ref = useRef(null);
  const isInView = useInView(ref, { once: false, amount: 0.5 });
  
  useEffect(() => {
    if (!isInView) {
        setDisplayText(''); // Reset when out of view
        return;
    }

    let iteration = 0;
    const interval = setInterval(() => {
      setDisplayText(text
        .split('')
        .map((letter, index) => {
          if (index < iteration) {
            return text[letter] || letter;
          }
          return characters[Math.floor(Math.random() * characters.length)];
        })
        .join('')
      );
      
      if (iteration >= text.length) {
        clearInterval(interval);
        setDisplayText(text);
      }
      
      iteration += 1 / 3;
    }, 30);
    
    return () => clearInterval(interval);
  }, [isInView, text]);

  return <span ref={ref} className={className}>{displayText}</span>;
};

const features = [
  {
    icon: Brain,
    title: "Contextual Understanding",
    desc: "LETA interprets query intent against thousands of statutory provisions in real-time."
  },
  {
    icon: ShieldCheck,
    title: "Verifiable Accuracy",
    desc: "Every response includes precise citations to Notification numbers and Act sections."
  },
  {
    icon: Zap,
    title: "Professional Grade",
    desc: "Designed exclusively for CAs and tax practitioners. No hallucinations, just data."
  }
];

const LetaIntro = () => {
  return (
    <section className="relative py-32 bg-[#020202] text-white overflow-hidden border-t border-white/5">
      {/* Neural Background Layer */}
      <NeuralBackground />
      
      {/* Gradient Vignette for seamless blending - STRICT DARK */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#020202] via-transparent to-[#020202] z-10 pointer-events-none" />

      <div className="relative z-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-20 text-center md:text-left">
           <motion.div
             initial={{ opacity: 0, y: 10 }}
             whileInView={{ opacity: 1, y: 0 }}
             viewport={{ once: false }}
             className="inline-flex items-center gap-2 py-1 px-3 mb-6 border border-sentinel-green/30 rounded bg-sentinel-green/5 backdrop-blur-md"
           >
              <div className="w-2 h-2 bg-sentinel-green rounded-full animate-ping" />
              <span className="text-[10px] font-mono text-sentinel-green tracking-[0.2em] font-bold uppercase">
                System Status: Active
              </span>
           </motion.div>

           <motion.h2 
             initial={{ opacity: 0, x: -20 }}
             whileInView={{ opacity: 1, x: 0 }}
             viewport={{ once: false }}
             transition={{ duration: 0.8 }}
             className="text-5xl md:text-7xl font-bold mb-4 tracking-tighter font-sans text-white uppercase"
           >
             <ScifiText text="INTRODUCING LETA" className="" />
           </motion.h2>

           <motion.div
              initial={{ opacity: 0, width: 0 }}
              whileInView={{ opacity: 1, width: "100%" }}
              viewport={{ once: false }}
              transition={{ delay: 0.5, duration: 1 }}
              className="h-[1px] bg-gradient-to-r from-sentinel-blue via-sentinel-green to-transparent max-w-xl mb-6"
           />

            {/* FULL FORM DECODING */}
           <motion.h3
             initial={{ opacity: 0 }}
             whileInView={{ opacity: 1 }}
             viewport={{ once: false }}
             transition={{ delay: 1 }}
             className="text-2xl md:text-3xl font-mono text-sentinel-blue mb-8 tracking-widest uppercase"
           >
              [ LEGAL TAXATION INTELLIGENCE ]
           </motion.h3>
           
           <motion.p 
             initial={{ opacity: 0 }}
             whileInView={{ opacity: 1 }}
             viewport={{ once: false }}
             transition={{ delay: 1.2 }}
             className="text-xl md:text-2xl text-gray-400 max-w-3xl font-light leading-relaxed border-l-2 border-white/10 pl-6"
           >
             LETA is not a chatbot. <br className="hidden md:block" />
             It is a <span className="text-white font-medium">statutory intelligence system</span>, <br className="hidden md:block" />
             embedded directly into professional GST workflows.
           </motion.p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {features.map((feature, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: false }}
              transition={{ duration: 0.5, delay: idx * 0.15 + 0.5 }} // Reduced delay for smoother re-entry
              className="p-8 border border-white/10 bg-[#050A10] hover:bg-white/5 hover:border-sentinel-green/50 transition-all duration-300 rounded-sm group relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 p-3 opacity-20 group-hover:opacity-100 transition-opacity">
                 <feature.icon size={48} strokeWidth={0.5} className="text-white" />
              </div>

              <div className="w-12 h-12 mb-6 flex items-center justify-center text-sentinel-green border border-sentinel-green/20 rounded-sm bg-sentinel-green/5 group-hover:scale-110 transition-transform duration-300">
                <feature.icon size={24} strokeWidth={1.5} />
              </div>
              <h3 className="text-lg font-bold text-white mb-3 font-mono tracking-wide uppercase border-b border-white/10 pb-2 inline-block">
                {feature.title}
              </h3>
              <p className="text-gray-400 leading-relaxed text-sm font-mono mt-2">
                {feature.desc}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default LetaIntro;
