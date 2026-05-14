import {
  FileText, Layers, BookOpen, Gavel, Book, Scroll, Globe, Info
} from 'lucide-react';
import React from 'react';

export const CATEGORY_GROUPS = [
  {
    title: 'GST STATUTORY ARCHIVES',
    rows: [
      { id: 'circulars',    label: 'Circulars & Notifications',   icon: Layers,   colorClass: 'colorCirculars',  accentClass: 'accentCirculars' },
      { id: 'aars',         label: 'Advance Rulings (AAR)',       icon: Gavel,    colorClass: 'colorAars',       accentClass: 'accentAars'   },
      { id: 'highcourt',    label: 'High Court Case Laws',        icon: Book,     colorClass: 'colorHighcourt',  accentClass: 'accentHighcourt'  },
      { id: 'supremecourt', label: 'Supreme Court Case Laws',     icon: Gavel,    colorClass: 'colorSupremecourt', accentClass: 'accentSupremecourt' },
    ],
  },
  {
    title: 'OPERATIONAL RESOURCES',
    rows: [
      { id: 'forms',     label: 'Statutory Forms',    icon: FileText, colorClass: 'colorForms',     accentClass: 'accentForms'   },
      { id: 'brochures', label: 'Official Brochures', icon: BookOpen, colorClass: 'colorBrochures', accentClass: 'accentBrochures' },
      { id: 'flyers',    label: 'Information Flyers', icon: Info,     colorClass: 'colorFlyers',    accentClass: 'accentFlyers'   },
    ],
  },
  {
    title: 'ACTS & FRAMEWORKS',
    rows: [
      { id: 'acts',  label: 'The GST Acts',          icon: Book,     colorClass: 'colorActs',  accentClass: 'accentActs' },
      { id: 'rules', label: 'Statutory Rules',       icon: Scroll,   colorClass: 'colorRules', accentClass: 'accentRules' },
      { id: 'cgst',  label: 'CGST Notifications',    icon: FileText, colorClass: 'colorCgst',  accentClass: 'accentCgst' },
      { id: 'igst',  label: 'IGST Notifications',    icon: Globe,    colorClass: 'colorIgst',  accentClass: 'accentIgst'   },
    ],
  },
];

export const FILTER_OPTIONS = [
  { id: 'all',          label: 'All Material' },
  { id: 'rules',        label: 'Acts & Rules' },
  { id: 'circulars',    label: 'Circulars & Notices' },
  { id: 'case-laws',    label: 'Appellate Cases' },
  { id: 'aar',          label: 'AAR Rulings' },
  { id: 'forms',        label: 'Forms & Briefs' },
];

export const TRENDING_SEARCHES = [
  'Rule 86A blocking',
  'Inverted duty refund',
  'Section 17(5)(c) construction',
  'Corporate Guarantee Taxability',
];

export const getDocumentContext = (title: string) => {
  const cleanTitle = title.replace('.pdf', '').toLowerCase();
  
  if (cleanTitle.includes('circular') || cleanTitle.includes('circ')) {
    return {
      type: 'CIRCULAR',
      summary: 'Central Board circular providing clarificatory directives and standard compliance audit guidelines.',
      sections: ['Section 168', 'Rule 36(4)'],
      authority: 'CBIC Office',
      date: 'June 2024',
    };
  }
  if (cleanTitle.includes('notification') || cleanTitle.includes('notif') || cleanTitle.includes('cgst-')) {
    return {
      type: 'NOTIFICATION',
      summary: 'Official statutory amendment altering filing limits, exemptions, and mandatory due-date schedules.',
      sections: ['Section 39', 'Rule 61'],
      authority: 'Ministry of Finance',
      date: 'May 2024',
    };
  }
  if (cleanTitle.includes('aar') || cleanTitle.includes('advance') || cleanTitle.includes('ruling')) {
    return {
      type: 'AAR RULING',
      summary: 'Advance authority decision resolving the classification of supply and tax rate applicability.',
      sections: ['Section 95', 'Schedule II'],
      authority: 'AAR Bench',
      date: 'March 2024',
    };
  }
  if (cleanTitle.includes('court') || cleanTitle.includes('gavel') || cleanTitle.includes('judg') || cleanTitle.includes('vs')) {
    return {
      type: 'JUDGMENT',
      summary: 'Appellate court decision ruling on input credit eligibility and constitutional validity.',
      sections: ['Section 17(5)', 'Article 226'],
      authority: 'High Court',
      date: 'Feb 2024',
    };
  }
  return {
    type: 'ACTS & RULES',
    summary: 'Consolidated statutory framework reference, central rule handbook, or official compliance circular.',
    sections: ['Section 9', 'Rule 21'],
    authority: 'GST Council',
    date: 'July 2017',
  };
};
