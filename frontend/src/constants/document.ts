import type { StatusColor } from './status';

export const DOCUMENT_STATUSES = ['Processed', 'Processing', 'Failed'] as const;
export type DocumentStatus = typeof DOCUMENT_STATUSES[number];

export const DOCUMENT_STATUS_LABEL: Record<DocumentStatus, string> = {
  Processed:  'Processed',
  Processing: 'Processing',
  Failed:     'Failed',
};

export const DOCUMENT_STATUS_COLOR: Record<DocumentStatus, StatusColor> = {
  Processed:  'positive',
  Processing: 'warning',
  Failed:     'negative',
};

export const DOCUMENT_STATUS_OPTIONS = DOCUMENT_STATUSES.map(value => ({
  value,
  label: DOCUMENT_STATUS_LABEL[value],
}));
