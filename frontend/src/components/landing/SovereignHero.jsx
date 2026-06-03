import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import FloatingParticles from '../effects/FloatingParticles';

import cx from 'classnames/bind';
import styles from './SovereignHero.module.css';

const cn = cx.bind(styles);

const STATS = [
  { number: '2,400+', label: 'GST Circulars' },
  { number: '14',     label: 'HC Jurisdictions' },
  { number: '99.2%',  label: 'Citation Accuracy' },
];


const SovereignHero = () => {
  return (
    <section className={cn('heroSection')}>

      {/* Floating particles background */}
      <FloatingParticles />

      {/* Ambient Floating Dust Particles */}
      <div className={cn('dustParticlesContainer')}>
        <div className={cn('dustParticle', 'p1')} />
        <div className={cn('dustParticle', 'p2')} />
        <div className={cn('dustParticle', 'p3')} />
        <div className={cn('dustParticle', 'p4')} />
        <div className={cn('dustParticle', 'p5')} />
        <div className={cn('dustParticle', 'p6')} />
      </div>

      <div className={cn('gridContainer')}>
        <div className={cn('grid')}>
          <div className={cn('leftColumn')}>

            {/* Hero Heading */}
            <motion.h1
              initial={{ opacity: 0, y: 25 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.9, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className={cn('heroHeading')}
            >
              Legal and TAX <br />
              <span className={cn('headingGradient')}>
                Assistant
              </span>
            </motion.h1>

            {/* Supporting Copy */}
            <motion.p
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.45 }}
              className={cn('supportingCopy')}
            >
              Hybrid Artificial Intelligence for litigation and Taxation — knowledge and experience based advisory, drafting and research.
            </motion.p>

            {/* CTA Elements */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.58 }}
              className={cn('ctaContainer')}
            >
              <Link to="/gst">
                <button className={cn('ctaButtonPrimary')}>
                  Start Consultation
                  <ChevronRight size={14} className={cn('chevronIcon')} />
                </button>
              </Link>
              <Link to="/about">
                <button className={cn('ctaButtonSecondary')}>
                  Learn More
                </button>
              </Link>
            </motion.div>


          </div>
        </div>
      </div>

      {/* Scroll Cue */}
      <motion.div
        className={cn('scrollCue')}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1, delay: 1.1 }}
      >
        <div className={cn('scrollLine')}>
          <div className={cn('scrollDot')} />
        </div>
      </motion.div>

    </section>
  );
};

export default SovereignHero;
