import React from 'react';
import { FileText, Code, Book } from 'lucide-react';
import { DocumentLibrary } from '../components/documents';

import cx from 'classnames/bind';
import styles from './Documentation.module.css';

const cn = cx.bind(styles);

const DOC_CARDS = [
  {
    icon: Book,
    title: 'User Guides',
    desc: 'Step-by-step tutorials on using the LETA interface, interpreting confidence scores, and managing citations.',
    link: 'View Guides',
  },
  {
    icon: Code,
    title: 'API Reference',
    desc: 'Technical documentation for accessing the Sentinel.AI knowledge graph programmatically.',
    link: 'Read API Docs',
  },
  {
    icon: FileText,
    title: 'Legal Disclaimers',
    desc: 'Terms of use, privacy policy, and liability limitations for AI-generated advisory.',
    link: 'Read Policy',
  },
];

const Documentation: React.FC = () => (
  <div className={cn('pageWrapper')}>
    <div className={cn('container')}>

      {/* Header */}
      <div className={cn('header')}>
        <h1 className={cn('title')}>
          LETA TITAN Knowledge Ops
        </h1>
        <p className={cn('subtitle')}>
          Secure statutory repository &amp; AI-powered legal intelligence network.
        </p>
      </div>

      {/* Document Library */}
      <div className={cn('libraryContainer')}>
        <DocumentLibrary />
      </div>

      {/* Info cards */}
      <div className={cn('grid')}>
        {DOC_CARDS.map(({ icon: Icon, title, desc, link }) => (
          <div
            key={title}
            className={cn('card')}
          >
            <div className={cn('iconWrapper')}>
              <Icon size={20} />
            </div>
            <div>
              <h3 className={cn('cardTitle')}>
                {title}
              </h3>
              <p className={cn('cardDesc')}>
                {desc}
              </p>
            </div>
            <a
              href="#"
              className={cn('cardLink')}
            >
              {link} →
            </a>
          </div>
        ))}
      </div>

    </div>
  </div>
);

export default Documentation;
