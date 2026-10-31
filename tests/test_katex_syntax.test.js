const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const katex = require('katex');

const WORKSPACE = path.resolve(__dirname, '..');

function extractFormulas(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  // Strip code blocks first
  const noCodeBlocks = content.replace(/```[\s\S]*?```/g, '').replace(/`[^`\n]+`/g, '');

  const formulas = [];

  // 1. Extract display math $$...$$
  const displayRegex = /\$\$([\s\S]*?)\$\$/g;
  let match;
  while ((match = displayRegex.exec(noCodeBlocks)) !== null) {
    const expr = match[1].trim();
    if (expr) {
      formulas.push({ expr, display: true });
    }
  }

  // Remove display blocks to isolate inline math
  const noDisplay = noCodeBlocks.replace(/\$\$[\s\S]*?\$\$/g, '');

  // 2. Extract inline math $...$ (ignore escaped \$ and bare prices like $100)
  const inlineRegex = /(?<!\\)\$([^\$\n]+?)(?<!\\)\$/g;
  while ((match = inlineRegex.exec(noDisplay)) !== null) {
    const expr = match[1].trim();
    // Exclude currency numbers like "100" or "50.00"
    if (expr && !/^\d+(?:\.\d+)?$/.test(expr)) {
      formulas.push({ expr, display: false });
    }
  }

  return formulas;
}

test('KaTeX AST Validation: docs/FORMULAS.md', () => {
  const formulasPath = path.join(WORKSPACE, 'docs', 'FORMULAS.md');
  assert.ok(fs.existsSync(formulasPath), 'docs/FORMULAS.md must exist');

  const formulas = extractFormulas(formulasPath);
  assert.ok(formulas.length > 0, 'Must extract at least one formula from docs/FORMULAS.md');

  for (const { expr, display } of formulas) {
    try {
      katex.renderToString(expr, { throwOnError: true, displayMode: display });
    } catch (err) {
      assert.fail(`KaTeX parse error in docs/FORMULAS.md for expression "${expr}": ${err.message}`);
    }
  }
});

test('KaTeX AST Validation: README.md', () => {
  const readmePath = path.join(WORKSPACE, 'README.md');
  assert.ok(fs.existsSync(readmePath), 'README.md must exist');

  const formulas = extractFormulas(readmePath);
  assert.ok(formulas.length > 0, 'Must extract at least one formula from README.md');

  for (const { expr, display } of formulas) {
    try {
      katex.renderToString(expr, { throwOnError: true, displayMode: display });
    } catch (err) {
      assert.fail(`KaTeX parse error in README.md for expression "${expr}": ${err.message}`);
    }
  }
});
