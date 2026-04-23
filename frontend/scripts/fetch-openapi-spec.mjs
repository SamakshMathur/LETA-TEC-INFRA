/**
 * Downloads the OpenAPI spec from the running FastAPI backend and saves it
 * to .orval/openapi.json so Orval can generate typed API clients without
 * requiring the backend to be up during CI or teammate onboarding.
 *
 * Usage:
 *   node scripts/fetch-openapi-spec.mjs
 *   API_URL=http://staging.example.com node scripts/fetch-openapi-spec.mjs
 */

import { writeFileSync, mkdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const API_URL = process.env.API_URL ?? 'http://localhost:8000';
const OUT_DIR = join(__dirname, '../.orval');
const OUT_FILE = join(OUT_DIR, 'openapi.json');

console.log(`Fetching OpenAPI spec from ${API_URL}/openapi.json …`);

let res;
try {
  res = await fetch(`${API_URL}/openapi.json`);
} catch (err) {
  console.error(`Could not reach backend at ${API_URL}: ${err.message}`);
  console.error('Make sure the FastAPI server is running before generating the API client.');
  process.exit(1);
}

if (!res.ok) {
  console.error(`Server returned ${res.status} ${res.statusText}`);
  process.exit(1);
}

const spec = await res.json();
mkdirSync(OUT_DIR, { recursive: true });
writeFileSync(OUT_FILE, JSON.stringify(spec, null, 2));
console.log(`Spec saved → ${OUT_FILE}`);
