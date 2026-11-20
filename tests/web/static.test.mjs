// Checks on the files themselves: no way to inject markup, no outside resources, no typos in ids.
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const WEB = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'src', 'linkfall', 'web');
const read = (path) => readFileSync(join(WEB, path), 'utf8');
const jsFiles = readdirSync(join(WEB, 'js')).filter((f) => f.endsWith('.js'));
const pages = readdirSync(WEB).filter((f) => f.endsWith('.html'));
const html = pages.map(read).join('\n');
const css = readdirSync(WEB).filter((f) => f.endsWith('.css')).map(read).join('\n');

test('scripts never build markup or run text as code (ASVS 1.3.2, 3.2.2)', () => {
  const banned = [/\.innerHTML/, /\.outerHTML/, /insertAdjacentHTML/, /document\.write/, /\beval\s*\(/, /new Function/, /setTimeout\s*\(\s*['"`]/, /createContextualFragment/];
  for (const file of jsFiles) {
    const code = read(join('js', file));
    for (const pattern of banned) assert.doesNotMatch(code, pattern, `${file} uses ${pattern}`);
  }
});

test('the pages have no inline script, no style attributes and no inline handlers', () => {
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
  assert.ok(scripts.length >= pages.length);
  for (const [, attrs, body] of scripts) {
    assert.match(attrs, /\bsrc="\/js\//);
    assert.equal(body.trim(), '');
  }
  assert.doesNotMatch(html, /<style\b/);
  assert.doesNotMatch(html, /\sstyle\s*=/);
  assert.doesNotMatch(html, /\son[a-z]+\s*=/i);
});

test('nothing is loaded from outside this server', () => {
  for (const [name, text] of [['the pages', html], ['the stylesheets', css], ...jsFiles.map((f) => [f, read(join('js', f))])]) {
    assert.doesNotMatch(text.replace(/xmlns="[^"]*"/g, ''), /https?:\/\/|@import|\/\/cdn\./i, name);
  }
});

// The scripts a page loads: its entry script and everything it imports from there, dynamic
// imports included (backend.js loads the browser backend only in the hosted build).
function scriptsOf(page) {
  const found = new Set();
  const queue = [...read(page).matchAll(/<script\b[^>]*\bsrc="\/js\/([^"]+)"/g)].map((m) => m[1]);
  while (queue.length > 0) {
    const file = queue.pop();
    if (found.has(file)) continue;
    found.add(file);
    for (const [, spec] of read(join('js', file)).matchAll(/(?:from |import\()'\.\/([^']+)'/g)) queue.push(spec);
  }
  return found;
}

test('every id a page\'s scripts ask for exists in that page, and no id is used twice', () => {
  assert.deepEqual([...pages].sort(), ['index.html', 'range.html']);
  for (const page of pages) {
    const all = [...read(page).matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]);
    const ids = new Set(all);
    assert.equal(ids.size, all.length, `${page} repeats an id`);
    for (const file of scriptsOf(page)) {
      for (const [, id] of read(join('js', file)).matchAll(/byId\('([^']+)'\)/g)) assert.ok(ids.has(id), `${page}: ${file} wants #${id}`);
    }
  }
});

test('every script is loaded by a page', () => {
  const loaded = new Set(pages.flatMap((page) => [...scriptsOf(page)]));
  for (const file of jsFiles) assert.ok(loaded.has(file), `${file} is loaded by no page`);
});

test('every asset the page, styles and scripts name is shipped', () => {
  const sources = [html, css, ...jsFiles.map((f) => read(join('js', f)))];
  const wanted = new Set(sources.flatMap((s) => [...s.matchAll(/\/assets\/[A-Za-z0-9._-]+\.(?:svg|png)/g)].map((m) => m[0])));
  assert.ok(wanted.size > 0);
  for (const path of wanted) assert.ok(existsSync(join(WEB, path)), `missing ${path}`);
  for (const svg of readdirSync(join(WEB, 'assets'))) {
    assert.doesNotMatch(readFileSync(join(WEB, 'assets', svg), 'utf8'), /<script|onload=|href="https?:/i, svg);
  }
});

test('every relative import points at a file that exists', () => {
  for (const file of jsFiles) {
    for (const [, spec] of read(join('js', file)).matchAll(/from '(\.\/[^']+)'/g)) {
      assert.ok(existsSync(join(WEB, 'js', spec)), `${file} imports ${spec}`);
    }
  }
});

test('every page keeps the accessibility basics', () => {
  for (const page of pages) {
    const text = read(page);
    assert.match(text, /<html lang="en">/, page);
    assert.match(text, /name="viewport"/, page);
    assert.match(text, /<title>[^<]+<\/title>/, page);
    assert.match(text, /<main\b[^>]*id="main"/, page);
    assert.match(text, /class="skip" href="#main"/, page);
    assert.match(text, /role="status" aria-live="polite"/, page);
  }
  assert.match(read('index.html'), /role="slider"[^>]*aria-label="Link value"/);
  assert.match(read('range.html'), /<h1\b/);
  assert.match(read('range.html'), /<caption\b/);
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /:focus-visible/);
});
