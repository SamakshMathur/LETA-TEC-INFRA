import React, { useRef } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { Link } from 'react-router-dom';
import { FileText, Landmark, Globe, Briefcase, ChevronRight, Activity } from 'lucide-react';

import cx from 'classnames/bind';
import styles from './StatutoryDomains.module.css';

const cn = cx.bind(styles);

const MODULES = [
  {
    num: '01',
    icon: FileText,
    title: 'GST Intelligence',
    desc: 'Domain-trained statutory intelligence for Indian GST, covering Acts, Rules, Notifications, Circulars, and judicial clarifications with expert-level citation fidelity.',
    status: 'live',
    indexLabel: 'STATUTORY INDEX RANGE',
    indexValue: '98.4%',
    indexWidth: '98.4%',
    href: '/gst',
    wide: true,
  },
  {
    num: '02',
    icon: Landmark,
    title: 'Income Tax',
    desc: 'Structured intelligence for compliance and automated statutory audit verification under Direct Tax laws.',
    status: 'soon',
    indexLabel: 'INDEX STATUS',
    indexValue: '35%',
    indexWidth: '35%',
    wide: false,
  },
  {
    num: '03',
    icon: Globe,
    title: 'FEMA Advisory',
    desc: 'Specialized compliance workflows, foreign exchange intelligence, and regulatory transaction mapping.',
    status: 'soon',
    indexLabel: 'BUILD PROGRESS',
    indexValue: '22%',
    indexWidth: '22%',
    wide: false,
  },
  {
    num: '04',
    icon: Briefcase,
    title: 'Company Law',
    desc: 'Compliance, corporate governance, filing validations, and procedural guidance for the Companies Act, 2013.',
    status: 'soon',
    indexLabel: 'PIPELINE STATUS',
    indexValue: '41%',
    indexWidth: '41%',
    wide: true,
  },
];

// ── 3D tilt card wrapper ────────────────────────────────────────────────────
const Card3D = ({ children, className, isLive }) => {
  const ref = useRef(null);

  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);
  const rawGlowX = useMotionValue(50);
  const rawGlowY = useMotionValue(50);
  const rawScale = useMotionValue(1);

  const springConfig = { stiffness: 280, damping: 28, mass: 0.6 };
  const rotateX = useSpring(useTransform(rawY, [-0.5, 0.5], [10, -10]), springConfig);
  const rotateY = useSpring(useTransform(rawX, [-0.5, 0.5], [-10, 10]), springConfig);
  const scale   = useSpring(rawScale, { stiffness: 300, damping: 25 });
  const glowX   = useSpring(rawGlowX, { stiffness: 200, damping: 30 });
  const glowY   = useSpring(rawGlowY, { stiffness: 200, damping: 30 });

  const handleMouseMove = (e) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    const x = (e.clientX - rect.left) / rect.width  - 0.5;
    const y = (e.clientY - rect.top)  / rect.height - 0.5;
    rawX.set(x);
    rawY.set(y);
    rawGlowX.set(((e.clientX - rect.left) / rect.width)  * 100);
    rawGlowY.set(((e.clientY - rect.top)  / rect.height) * 100);
  };

  const handleMouseEnter = () => rawScale.set(1.035);
  const handleMouseLeave = () => {
    rawX.set(0);
    rawY.set(0);
    rawGlowX.set(50);
    rawGlowY.set(50);
    rawScale.set(1);
  };

  const specularBg = useTransform(
    [glowX, glowY],
    ([x, y]) =>
      `radial-gradient(circle at ${x}% ${y}%, rgba(255,255,255,0.07) 0%, transparent 60%)`
  );

  return (
    <motion.div
      ref={ref}
      style={{
        rotateX,
        rotateY,
        scale,
        transformStyle: 'preserve-3d',
        transformPerspective: 900,
      }}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={className}
    >
      {children}
      {/* Specular highlight follows cursor */}
      <motion.div
        style={{
          background: specularBg,
          position: 'absolute',
          inset: 0,
          borderRadius: 'inherit',
          pointerEvents: 'none',
          zIndex: 20,
        }}
      />
    </motion.div>
  );
};

const StatutoryDomains = () => {
  return (
    <section className={cn('section')}>
      <div className={cn('container')}>

        {/* Section header */}
        <div className={cn('headerRow')}>
          <div>
            <h2 className={cn('title')}>Statutory Intelligence Modules</h2>
            <div className={cn('statusIndicator')}>
              <Activity size={12} className="animate-pulse" />
              <span>Jurisdiction Network: Connected</span>
            </div>
          </div>
          <p className={cn('matrixLabel')}>// Active Intelligence Matrix</p>
        </div>

        {/* Bento Grid */}
        <div className={cn('grid')}>
          {MODULES.map((mod, i) => {
            const Icon = mod.icon;
            const isLive = mod.status === 'live';
            return (
              <motion.div
                key={mod.num}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.65, delay: i * 0.08, ease: [0.16, 1, 0.3, 1] }}
              >
                <Card3D
                  isLive={isLive}
                  className={cn('bentoCard', mod.wide ? 'cardWide' : 'cardNarrow', isLive && 'cardLive')}
                >
                  {/* Corner brackets */}
                  <span className={cn('cornerTL')} />
                  <span className={cn('cornerBR')} />

                  {/* Watermark icon */}
                  <div className={cn('cardIconWatermark')}>
                    <Icon size={mod.wide ? 240 : 180} strokeWidth={1} />
                  </div>

                  {/* Top accent line — live cards only */}
                  {isLive && <div className={cn('topAccentLine')} />}

                  {/* Header row */}
                  <div className={cn('cardHeader')}>
                    <div className={cn('headerLeft')}>
                      <span className={cn('moduleNumber')}>{mod.num}</span>
                      <div className={cn('iconWrapper', isLive && 'iconWrapperLive')}>
                        <Icon size={22} strokeWidth={1.5} style={{ color: isLive ? 'var(--color-brand)' : 'var(--color-text-muted)' }} />
                      </div>
                    </div>
                    {isLive ? (
                      <span className={cn('activeBadge')}>
                        <span className={cn('badgePulseDot')} />
                        Active Node
                      </span>
                    ) : (
                      <span className={cn('comingSoonBadge')}>Coming Soon</span>
                    )}
                  </div>

                  {/* Content */}
                  <div className={cn('cardBody')}>
                    <h3 className={cn('cardTitle')}>{mod.title}</h3>
                    <p className={cn('cardDesc', !isLive && 'cardDescMuted')}>{mod.desc}</p>
                  </div>

                  {/* Footer */}
                  <div className={cn('cardFooter')}>
                    <div className={cn('progressContainer')}>
                      <div className={cn('progressMeta')}>
                        <span>{mod.indexLabel}</span>
                        <span className={cn(isLive ? 'progressValueLive' : 'progressValueMuted')}>{mod.indexValue}</span>
                      </div>
                      <div className={cn('progressTrack')}>
                        <motion.div
                          initial={{ width: 0 }}
                          whileInView={{ width: mod.indexWidth }}
                          viewport={{ once: true }}
                          transition={{ duration: 1.4, ease: 'easeOut', delay: 0.3 }}
                          className={cn(isLive ? 'progressThumb' : 'progressThumbMuted')}
                        />
                      </div>
                    </div>

                    {isLive && (
                      <Link to={mod.href} className={cn('initializeBtn')}>
                        Initialize Workspace <ChevronRight size={13} />
                      </Link>
                    )}
                  </div>
                </Card3D>
              </motion.div>
            );
          })}
        </div>

      </div>
    </section>
  );
};

export default StatutoryDomains;
