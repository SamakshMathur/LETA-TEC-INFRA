import { FileText, Code, Book } from 'lucide-react';
import { DocumentLibrary } from '../components/documents';

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

const Documentation = () => (
  <div className="min-h-screen pt-28 pb-16" style={{ backgroundColor: 'var(--surface)' }}>
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">

      {/* Header */}
      <div className="text-center mb-14">
        <h1
          className="font-display font-bold text-4xl mb-3 tracking-tight uppercase"
          style={{ color: '#e5e2e1' }}
        >
          LETA TITAN Knowledge Ops
        </h1>
        <p className="font-mono text-xs tracking-widest uppercase" style={{ color: '#9a9a9a' }}>
          Secure statutory repository &amp; AI-powered legal intelligence network.
        </p>
      </div>

      {/* Document Library */}
      <div
        className="mb-16 rounded overflow-hidden"
        style={{ backgroundColor: 'var(--surface-container-low)' }}
      >
        <DocumentLibrary />
      </div>

      {/* Info cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
        {DOC_CARDS.map(({ icon: Icon, title, desc, link }) => (
          <div
            key={title}
            className="rounded p-8 flex flex-col gap-5 group transition-all duration-300 cursor-pointer"
            style={{ backgroundColor: 'var(--surface-container-high)' }}
            onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'var(--surface-bright)'; }}
            onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'var(--surface-container-high)'; }}
          >
            <div
              className="w-11 h-11 rounded flex items-center justify-center transition-colors"
              style={{ backgroundColor: 'var(--surface-container-lowest)' }}
            >
              <Icon size={20} style={{ color: '#9a9a9a' }} />
            </div>
            <div>
              <h3 className="font-semibold text-lg mb-2 transition-colors" style={{ color: '#e5e2e1' }}>
                {title}
              </h3>
              <p className="text-sm font-light leading-relaxed" style={{ color: '#9a9a9a' }}>
                {desc}
              </p>
            </div>
            <a
              href="#"
              className="text-sm font-semibold transition-colors mt-auto"
              style={{ color: '#4edea3' }}
              onMouseEnter={e => { e.currentTarget.style.color = '#e5e2e1'; }}
              onMouseLeave={e => { e.currentTarget.style.color = '#4edea3'; }}
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
