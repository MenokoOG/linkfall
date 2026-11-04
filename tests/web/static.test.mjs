// Checks on the files themselves: no way to inject markup, no outside resources, no typos in ids.
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const WEB = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'src', 'linkfall', 'web');
const read = (path) => readFileSync(join(WEB, path), 'utf8');
const jsFiles = readdirSync(join(WEB, 'js')).filter((f) => f.endsWith('.js'));
const html = read('index.html');
const css = read('styles.css');

test('scripts never build markup or run text as code (ASVS 1.3.2, 3.2.2)', () => {
  const banned = [/\.innerHTML/, /\.outerHTML/, /insertAdjacentHTML/, /document\.write/, /\beval\s*\(/, /new Function/, /setTimeout\s*\(\s*['"`]/, /createContextualFragment/];
  for (const file of jsFiles) {
    const code = read(join('js', file));
    for (const pattern of banned) assert.doesNotMatch(code, pattern, `${file} uses ${pattern}`);
  }
});

test('the page has no inline script, no style attributes and no inline handlers', () => {
  const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)];
  assert.ok(scripts.length >= 1);
  for (const [, attrs, body] of scripts) {
    assert.match(attrs, /\bsrc="\/js\//);
    assert.equal(body.trim(), '');
  }
  assert.doesNotMatch(html, /<style\b/);
  assert.doesNotMatch(html, /\sstyle\s*=/);
  assert.doesNotMatch(html, /\son[a-z]+\s*=/i);
});

test('nothing is loaded from outside this server', () => {
  for (const [name, text] of [['index.html', html], ['styles.css', css], ...jsFiles.map((f) => [f, read(join('js', f))])]) {
    assert.doesNotMatch(text.replace(/xmlns="[^"]*"/g, ''), /https?:\/\/|@import|\/\/cdn\./i, name);
  }
});

test('every id the scripts ask for exists in the page', () => {
  const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));
  for (const file of jsFiles) {
    for (const [, id] of read(join('js', file)).matchAll(/byId\('([^']+)'\)/g)) assert.ok(ids.has(id), `${file} wants #${id}`);
  }
});

test('every asset the page, styles and scripts name is shipped', () => {
  const sources = [html, css, ...jsFiles.map((f) => read(join('js', f)))];
  const wanted = new Set(sources.flatMap((s) => [...s.matchAll(/\/assets\/[A-Za-z0-9._-]+/g)].map((m) => m[0])));
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

test('the page keeps the accessibility basics', () => {
  assert.match(html, /<html lang="en">/);
  assert.match(html, /name="viewport"/);
  assert.match(html, /role="slider"[^>]*aria-label="Link value"/);
  assert.match(html, /<main\b/);
  assert.match(html, /class="skip"/);
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /:focus-visible/);
});
