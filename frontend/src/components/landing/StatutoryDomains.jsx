import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { FileText, Landmark, Globe, Briefcase, ChevronRight, Activity } from 'lucide-react';

import cx from 'classnames/bind';
import styles from './StatutoryDomains.module.css';

const cn = cx.bind(styles);

const StatutoryDomains = () => {
  return (
    <section className={cn('section')}>

      <div className={cn('container')}>

        {/* Section header — typography-driven spacing */}
        <div className={cn('headerRow')}>
          <div>
            <h2 className={cn('title')}>
              Statutory Intelligence Modules
            </h2>
            <div className={cn('statusIndicator')}>
              <Activity size={12} className="animate-pulse" />
              <span>Jurisdiction Network: Connected</span>
            </div>
          </div>
          <p className={cn('matrixLabel')}>
            // ACTIVE INTELLIGENCE MATRIX
          </p>
        </div>

        {/* Bento Grid layout */}
        <div className={cn('grid')}>

          {/* Card 1: GST Intelligence (Flagship - Wide Bento Block) */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className={cn('bentoCard', 'cardWide')}
          >
            {/* Background absolute elements */}
            <div className={cn('cardIconWatermark')}>
              <FileText size={240} strokeWidth={1} />
            </div>

            {/* Top row */}
            <div>
              <div className={cn('cardHeader')}>
                <div className={cn('iconWrapper')}>
                  <FileText size={26} strokeWidth={1.5} style={{ color: 'var(--color-brand)' }} />
                </div>
                <span className={cn('activeBadge')}>
                  <span className={cn('badgePulseDot')} />
                  Active Node
                </span>
              </div>

              {/* Title & info */}
              <h3 className={cn('cardTitle', 'cardTitleLarge')}>
                GST Intelligence
              </h3>
              <p className={cn('cardDesc')}>
                Domain-trained statutory intelligence for Indian GST, covering Acts, Rules, Notifications, Circulars, and judicial clarifications with expert-level citation fidelity.
              </p>
            </div>

            {/* Bottom elements */}
            <div className={cn('cardFooterRow')}>
              {/* Micro bar progress tracker */}
              <div className={cn('progressContainer')}>
                <div className={cn('progressMeta')}>
                  <span>STATUTORY INDEX RANGE</span>
                  <span className={cn('progressBarLabelAccent')}>98.4%</span>
                </div>
                <div className={cn('progressTrack')}>
                  <motion.div
                    initial={{ width: 0 }}
                    whileInView={{ width: '98.4%' }}
                    viewport={{ once: true }}
                    transition={{ duration: 1.5, ease: 'easeOut', delay: 0.2 }}
                    className={cn('progressThumb')}
                  />
                </div>
              </div>

              <Link to="/gst" className={cn('initializeBtn')}>
                Initialize Workspace <ChevronRight size={14} />
              </Link>
            </div>
          </motion.div>

          {/* Card 2: Income Tax (Standard Bento Block) */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className={cn('bentoCard', 'cardNarrow')}
          >
            <div>
              <div className={cn('cardHeader')}>
                <div className={cn('iconWrapper')}>
                  <Landmark size={26} strokeWidth={1.5} style={{ color: 'var(--color-text-muted)' }} />
                </div>
                <span className={cn('comingSoonBadge')}>
                  Coming Soon
                </span>
              </div>

              <h3 className={cn('cardTitle')}>
                Income Tax
              </h3>
              <p className={cn('cardDesc', 'cardDescMuted')}>
                Structured intelligence for compliance and automated statutory audit verification under Direct Tax laws.
              </p>
            </div>

            {/* Bottom elements */}
            <div className={cn('cardFooterSimple')}>
              <div className={cn('progressContainer')}>
                <div className={cn('progressMeta')}>
                  <span>INDEX STATUS</span>
                  <span>PENDING DEPLOYMENT</span>
                </div>
                <div className={cn('progressTrack')}>
                  <div className={cn('progressThumbMuted')} style={{ width: '35%' }} />
                </div>
              </div>
            </div>
          </motion.div>

          {/* Card 3: FEMA Advisory (Standard Bento Block) */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className={cn('bentoCard', 'cardNarrow')}
          >
            <div>
              <div className={cn('cardHeader')}>
                <div className={cn('iconWrapper')}>
                  <Globe size={26} strokeWidth={1.5} style={{ color: 'var(--color-text-muted)' }} />
                </div>
                <span className={cn('comingSoonBadge')}>
                  Coming Soon
                </span>
              </div>

              <h3 className={cn('cardTitle')}>
                FEMA Advisory
              </h3>
              <p className={cn('cardDesc', 'cardDescMuted')}>
                Specialized compliance workflows, foreign exchange intelligence, and regulatory transaction mapping.
              </p>
            </div>

            {/* Bottom pagination tracker elements */}
            <div className={cn('paginationRow')}>
              <span className={cn('paginationDot')} />
              <span className={cn('paginationDot', 'paginationDotActive')} />
              <span className={cn('paginationDot')} />
              <span className={cn('paginationText')}>
                Module Indexing In Progress
              </span>
            </div>
          </motion.div>

          {/* Card 4: Company Law (Wide Bento Block) */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.1 }}
            className={cn('bentoCard', 'cardWide')}
          >
            {/* Background shield asset */}
            <div className={cn('cardIconWatermark')}>
              <Briefcase size={220} strokeWidth={1} />
            </div>

            <div>
              <div className={cn('cardHeader')}>
                <div className={cn('iconWrapper')}>
                  <Briefcase size={26} strokeWidth={1.5} style={{ color: 'var(--color-text-muted)' }} />
                </div>
                <span className={cn('comingSoonBadge')}>
                  Coming Soon
                </span>
              </div>

              <h3 className={cn('cardTitle', 'cardTitleLarge')}>
                Company Law
              </h3>
              <p className={cn('cardDesc', 'cardDescMuted')}>
                Compliance, corporate governance, filing validations, and procedural guidance for the Companies Act, 2013. Designed for seamless structural analysis.
              </p>
            </div>

            {/* Bottom metadata tag line */}
            <div className={cn('metaRow')}>
              <span className={cn('metaText', 'metaTextTracking')}>
                // SECURED_COMPLIANCE_SHIELD_READY
              </span>
              <span className={cn('metaText')}>
                v1.0.4 DEV_BUILD
              </span>
            </div>
          </motion.div>

        </div>
      </div>
    </section>
  );
};

export default StatutoryDomains;
