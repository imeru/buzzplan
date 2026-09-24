#!/usr/bin/env node
// assets/src/editor/index.js -> assets/vendor/buzzplan-editor.mjs (단일 ESM 번들).
// esbuild(핀 고정, MIT)만 쓰고 다른 번들러/로더는 두지 않는다.
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');

const entry = path.join(root, 'assets/src/editor/index.js');
const outfile = path.join(root, 'assets/vendor/buzzplan-editor.mjs');

const isDev = process.argv.includes('--dev');

const result = await build({
  entryPoints: [entry],
  outfile,
  bundle: true,
  format: 'esm',
  platform: 'browser',
  target: ['es2020'],
  minify: !isDev,
  sourcemap: isDev ? 'inline' : false,
  legalComments: 'none',
  metafile: true,
  logLevel: 'info',
});

const bytes = fs.statSync(outfile).size;
console.log(`[build-editor] wrote ${path.relative(root, outfile)} (${bytes.toLocaleString()} bytes, ${(bytes / 1024).toFixed(1)} KB)`);

if (process.env.BZP_WRITE_METAFILE) {
  fs.writeFileSync(path.join(root, 'assets/vendor/buzzplan-editor.meta.json'), JSON.stringify(result.metafile, null, 2));
}
