#!/usr/bin/env node
// assets/src/editor/**/*.js 전부와 생성된 assets/vendor/buzzplan-editor.mjs를
// `node --check`로 구문 검사한다. index.html은 이 저장소의 관행대로
// 별도 절차(9장 1번, python3 + node --check /tmp/app.js)로 검사하므로 건드리지 않는다.
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import fs from 'node:fs';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (entry.isFile() && /\.m?js$/.test(entry.name)) out.push(full);
  }
  return out;
}

const targets = [
  ...walk(path.join(root, 'assets/src/editor')),
  ...walk(path.join(root, 'scripts')),
];

const vendorBundle = path.join(root, 'assets/vendor/buzzplan-editor.mjs');
if (fs.existsSync(vendorBundle)) targets.push(vendorBundle);

let failed = 0;
for (const file of targets) {
  try {
    execFileSync(process.execPath, ['--check', file], { stdio: 'pipe' });
    console.log(`ok    ${path.relative(root, file)}`);
  } catch (err) {
    failed += 1;
    console.error(`FAIL  ${path.relative(root, file)}`);
    console.error(err.stderr?.toString() || err.message);
  }
}

console.log(`\n${targets.length - failed}/${targets.length} passed syntax check`);
if (failed > 0) process.exit(1);
