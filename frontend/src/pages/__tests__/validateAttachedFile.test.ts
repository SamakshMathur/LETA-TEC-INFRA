import { describe, it, expect } from 'vitest';
import { validateAttachedFile, ACCEPTED_FILE_EXTENSIONS, MAX_FILE_SIZE_BYTES } from '../LetaWorkspace';

/**
 * Regression coverage for a real gap found during a flow audit: nothing
 * checked a file's size or type before attempting to attach/upload it —
 * an oversized or unsupported file only failed after the FULL POST
 * completed, surfacing through the same generic "Unable to reach the
 * advisory server" message as any other network error, with no
 * file-specific explanation and no immediate feedback.
 */

function makeFile(name: string, sizeBytes: number, type = 'application/octet-stream'): File {
  const file = new File([new Uint8Array(1)], name, { type });
  // jsdom's File doesn't let the constructor set an arbitrary large size
  // via content — override the getter directly instead of allocating a
  // real multi-MB buffer per test.
  Object.defineProperty(file, 'size', { value: sizeBytes, configurable: true });
  return file;
}

describe('validateAttachedFile', () => {
  it('accepts every extension the backend actually supports', () => {
    for (const ext of ACCEPTED_FILE_EXTENSIONS) {
      const file = makeFile(`document${ext}`, 1024);
      expect(validateAttachedFile(file)).toBeNull();
    }
  });

  it('rejects an unsupported extension with a clear, specific message', () => {
    const file = makeFile('archive.zip', 1024);
    const error = validateAttachedFile(file);
    expect(error).not.toBeNull();
    expect(error).toContain('archive.zip');
    expect(error).toContain('supported file type');
  });

  it('rejects a file over the 20 MB server limit', () => {
    const file = makeFile('huge.pdf', MAX_FILE_SIZE_BYTES + 1);
    const error = validateAttachedFile(file);
    expect(error).not.toBeNull();
    expect(error).toContain('20 MB');
  });

  it('accepts a file exactly at the 20 MB limit', () => {
    const file = makeFile('exact.pdf', MAX_FILE_SIZE_BYTES);
    expect(validateAttachedFile(file)).toBeNull();
  });

  it('is case-insensitive on the extension', () => {
    const file = makeFile('SCAN.PDF', 1024);
    expect(validateAttachedFile(file)).toBeNull();
  });

  it('rejects a file with no extension at all', () => {
    const file = makeFile('README', 1024);
    expect(validateAttachedFile(file)).not.toBeNull();
  });
});
