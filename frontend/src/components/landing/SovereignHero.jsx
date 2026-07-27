import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, ChevronRight } from 'lucide-react';
import IsometricCubeField from '../effects/IsometricCubeField';
import HeroMeshBackground from '../effects/HeroMeshBackground';
import MagneticButton from '../ui/MagneticButton';
import { useCountUp } from '../../hooks/useCountUp';

import cx from 'classnames/bind';
import styles from './SovereignHero.module.css';

const cn = cx.bind(styles);

/* ── Word-by-word kinetic reveal ───────────────────────────────────────── */
const KineticHeading = ({ children, delay = 0, className }) => {
  const words = String(children).split(' ');
  return (
    <span className={className}>
      {words.map((word, i) => (
        <span
          key={i}
          style={{ display: 'inline-block', overflow: 'hidden', verticalAlign: 'bottom', paddingBottom: '0.05em' }}
        >
          <motion.span
            style={{ display: 'inline-block' }}
            initial={{ opacity: 0, y: '105%', filter: 'blur(10px)' }}
            animate={{ opacity: 1, y: '0%', filter: 'blur(0px)' }}
            transition={{ duration: 0.72, delay: delay + i * 0.07, ease: [0.16, 1, 0.3, 1] }}
          >
            {word}{i < words.length - 1 ? ' ' : ''}
          </motion.span>
        </span>
      ))}
    </span>
  );
};

/* ── Stat counter ──────────────────────────────────────────────────────── */
const StatItem = ({ numeric, suffix, label, delay = 0, decimals = 0 }) => {
  const { count, ref } = useCountUp(numeric, 2000, decimals);
  const displayed = decimals > 0
    ? count.toFixed(decimals)
    : Math.floor(count).toLocaleString();
  return (
    <motion.div
      ref={ref}
      className={cn('statItem')}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      <span className={cn('statNumber')}>{displayed}{suffix}</span>
      <span className={cn('statLabel')}>{label}</span>
    </motion.div>
  );
};

const STATS = [
  { numeric: 2400,  suffix: '+',  label: 'Legal Circulars',   delay: 1.2, decimals: 0 },
  { numeric: 14,    suffix: '',   label: 'HC Jurisdictions',  delay: 1.3, decimals: 0 },
  { numeric: 99.2,  suffix: '%',  label: 'Citation Accuracy', delay: 1.4, decimals: 1 },
];

/* ── Main Component ─────────────────────────────────────────────────────── */
const SovereignHero = () => {
  return (
    <section className={cn('heroSection')}>

      {/* CSS gradient mesh — soft ambient glow */}
      <HeroMeshBackground />

      {/* 3D isometric cube field */}
      <IsometricCubeField />

      {/* Dark overlay so text stays readable over cubes */}
      <div className={cn('cubeOverlay')} aria-hidden="true" />

      {/* Ambient depth orbs */}
      <div className={cn('bgDepthBlurOrb1')} aria-hidden="true" />
      <div className={cn('bgDepthBlurOrb2')} aria-hidden="true" />
      <div className={cn('bgLensFlare')}     aria-hidden="true" />

      <div className={cn('gridContainer')}>
        <div className={cn('heroGrid')}>

          {/* ── Left: text content ──────────────────────────────────────── */}
          <div className={cn('leftColumn')}>

            {/* Eyebrow badge */}
            <motion.div
              className={cn('eyebrowWrapper')}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.1 }}
            >
              <span className={cn('eyebrowDot')} />
              <span className={cn('eyebrowText')}>Engine V2.4 Active</span>
            </motion.div>

            {/* Headline */}
            <h1 className={cn('heroHeading')}>
              <KineticHeading delay={0.2} className={cn('headingLine')}>
                Intelligence
              </KineticHeading>
              <KineticHeading delay={0.32} className={cn('headingLine')}>
                for High-Stakes
              </KineticHeading>
              <KineticHeading delay={0.44} className={cn('headingLineAccent')}>
                Legal &amp; Tax Matters.
              </KineticHeading>
            </h1>

            {/* Body copy */}
            <motion.p
              className={cn('supportingCopy')}
              initial={{ opacity: 0, y: 12, filter: 'blur(6px)' }}
              animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
              transition={{ duration: 0.9, delay: 0.68, ease: [0.16, 1, 0.3, 1] }}
            >
              AI-powered legal and tax research — GST, Income Tax, FEMA,
              and Company Law — built for precision-engineered advisory.
            </motion.p>

            {/* CTAs */}
            <motion.div
              className={cn('ctaStack')}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.8, delay: 0.84, ease: [0.16, 1, 0.3, 1] }}
            >
              <MagneticButton strength={0.22} className={cn('ctaFullWidth')}>
                <Link to="/dashboard" className={cn('ctaButtonPrimary')}>
                  <span>Enter Command Center</span>
                  <ArrowRight size={16} />
                  <span className={cn('ctaButtonShine')} />
                </Link>
              </MagneticButton>

              <MagneticButton strength={0.18} className={cn('ctaFullWidth')}>
                <Link to="/about" className={cn('ctaButtonSecondary')}>
                  <span>View Capabilities</span>
                  <ChevronRight size={14} style={{ opacity: 0.5 }} />
                </Link>
              </MagneticButton>
            </motion.div>

            {/* Stats */}
            <div className={cn('statsRow')}>
              {STATS.map((stat, i) => (
                <React.Fragment key={stat.label}>
                  <StatItem {...stat} />
                  {i < STATS.length - 1 && <div className={cn('statDivider')} />}
                </React.Fragment>
              ))}
            </div>

          </div>

          {/* ── Right: cube grid lives in the absolute background ────────── */}
          <div className={cn('rightColumn')} aria-hidden="true" />

        </div>
      </div>

      {/* Scroll cue */}
      <motion.div
        className={cn('scrollCue')}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1, delay: 1.5 }}
      >
        <div className={cn('scrollLine')}>
          <div className={cn('scrollDot')} />
        </div>
      </motion.div>

    </section>
  );
};

export default SovereignHero;
