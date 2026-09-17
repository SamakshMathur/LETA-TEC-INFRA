import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'fs';
import { join } from 'path';

/**
 * Regression coverage for a real, widespread WCAG failure found while
 * auditing readability feedback: '#374151' and '#475569' were the de facto
 * "muted secondary text" colors used across ~15 files (LetaWorkspace,
 * Settings, Payment, InvoiceHistory, ModuleDashboard, DocumentViewer,
 * AdvisoryModal, and more) — but both measure well under WCAG AA's 3:1
 * minimum (for UI text) against this app's near-black backgrounds:
 *   #374151 vs #000000 ≈ 2.04:1
 *   #475569 vs #000000 ≈ 2.77:1
 * '#64748B' (≈4.4:1, already the established replacement from PR #72's
 * WCAG contrast fixes) is the correct muted-secondary tone to use instead.
 *
 * This scans the whole src tree rather than one file, since the bug was
 * never confined to a single component — a narrower per-file test would
 * have missed most of these when the pattern was originally introduced.
 */

const SRC_DIR = join(__dirname, '..');
const FAILING_COLORS = ['#374151', '#475569'];
const EXTENSIONS = ['.tsx', '.ts', '.jsx'];

function collectSourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === '__tests__' || entry === 'node_modules') continue;
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      collectSourceFiles(full, out);
    } else if (EXTENSIONS.some(ext => entry.endsWith(ext))) {
      out.push(full);
    }
  }
  return out;
}

describe('no low-contrast text colors reintroduced', () => {
  const files = collectSourceFiles(SRC_DIR);

  it.each(FAILING_COLORS)('%s is not used anywhere as a text/placeholder color', (color) => {
    const offenders: string[] = [];
    for (const file of files) {
      const content = readFileSync(file, 'utf-8');
      // Only flag it as TEXT usage — a decorative background/border swatch
      // (e.g. a tiny status dot) isn't a readability problem the same way,
      // and ModuleDashboard.tsx deliberately keeps one such background dot.
      const textUsagePattern = new RegExp(
        `color:\\s*['"]${color}['"]|text-\\[${color}\\]|placeholder-\\[${color}\\]`,
        'i'
      );
      if (textUsagePattern.test(content)) {
        offenders.push(file.replace(SRC_DIR, 'src'));
      }
    }
    expect(offenders).toEqual([]);
  });
});
