// playwright: loads every page this PR adds or changes (plus the homepage as a
// smoke test) from a local static server, at desktop width and at 390px.
//
// Fails on: a non-200 page, a console error or uncaught exception, a broken
// internal link, a broken image, a broken external link on a changed page,
// an axe colour-contrast violation, or horizontal overflow at 390px.
//
//   node site-check.mjs <port> <path> [<path> ...]
//
// Paths are repo paths (blog/x/index.html); they are mapped to URLs here.
//
// The browser resolves alphageninsurance.com to the local server, so pages run
// under their real hostname. Cloudflare Turnstile is locked to that hostname
// and throws error 110200 on localhost, which would fail every quote page.

import { appendFileSync } from 'node:fs';
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';

const [port, ...paths] = process.argv.slice(2);
const base = 'http://alphageninsurance.com';
const toUrl = (p) => (p === 'index.html' ? '/' : p.endsWith('/index.html')
  ? '/' + p.slice(0, -'index.html'.length) : '/' + p);
const pages = [...new Set(['/', ...paths.map(toUrl)])];
const changed = new Set(paths.map(toUrl));

const VIEWPORTS = [
  { name: 'desktop', width: 1280, height: 900 },
  { name: '390px', width: 390, height: 844 },
];
// Hosts that refuse automated requests outright. A 401/403/429/999 from them
// is reported as a note, not a failure; a 404 or a dead host still fails.
const BOT_WALL = new Set([401, 403, 429, 999]);

const failures = [];
const notes = [];
const fail = (url, msg) => failures.push(`\`${url}\`: ${msg}`);

const browser = await chromium.launch({
  args: [`--host-resolver-rules=MAP alphageninsurance.com 127.0.0.1:${port}, MAP www.alphageninsurance.com 127.0.0.1:${port}`],
});
const linkCache = new Map();

async function checkLink(request, href, external) {
  if (linkCache.has(href)) return linkCache.get(href);
  let result;
  try {
    let res = await request.head(href, { timeout: 20000, maxRedirects: 10 });
    if (res.status() >= 400) res = await request.get(href, { timeout: 20000, maxRedirects: 10 });
    result = res.status();
  } catch (e) {
    result = external ? `unreachable (${e.message.split('\n')[0]})` : 'unreachable';
  }
  linkCache.set(href, result);
  return result;
}

for (const path of pages) {
  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const page = await context.newPage();
    const where = `${path} @ ${vp.name}`;
    const errors = [];
    // A console error from the site's own code or files fails the check. One
    // from a third party (Turnstile logs a junk line on purpose; Google's
    // tags occasionally drop a connection) is a note: the PR cannot fix it.
    page.on('console', (m) => {
      if (m.type() !== 'error') return;
      const src = m.location().url || '';
      if (src && !src.startsWith(base)) notes.push(`\`${where}\`: third-party console error from ${new URL(src).host}: ${m.text().slice(0, 120)}`);
      else errors.push(m.text());
    });
    page.on('pageerror', (e) => errors.push(`uncaught: ${e.message}`));

    const res = await page.goto(base + path, { waitUntil: 'load', timeout: 45000 });
    if (!res || res.status() !== 200) {
      fail(where, `returned ${res ? res.status() : 'no response'}`);
      await context.close();
      continue;
    }
    await page.waitForTimeout(1500);

    for (const e of errors) fail(where, `console error: ${e.slice(0, 200)}`);

    // Images: every <img> must have actually decoded.
    const badImgs = await page.$$eval('img', (imgs) => imgs
      .filter((i) => i.complete && i.naturalWidth === 0)
      .map((i) => i.getAttribute('src')));
    for (const src of badImgs) fail(where, `broken image ${src}`);

    // Overflow: nothing may push the page wider than the viewport.
    if (vp.width === 390) {
      const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (over > 0) fail(where, `horizontal overflow of ${over}px at 390px`);
    }

    // Contrast: axe's colour-contrast rule over the whole page.
    const axe = await new AxeBuilder({ page }).withRules(['color-contrast']).analyze();
    for (const v of axe.violations) {
      for (const n of v.nodes) fail(where, `contrast: ${n.target.join(' ')} — ${n.any[0]?.message ?? v.help}`);
    }

    // Links, once per page (desktop pass only). Internal links on every
    // tested page; external links only on pages this PR changed.
    if (vp.name === 'desktop') {
      const hrefs = await page.$$eval('a[href]', (as) => as.map((a) => a.href));
      for (const href of [...new Set(hrefs)]) {
        if (!/^https?:/.test(href)) continue; // tel:, mailto:, #fragment
        const url = href.split('#')[0];
        const internal = /^https?:\/\/(www\.)?alphageninsurance\.com\//.test(url);
        if (!internal && !changed.has(path)) continue;
        // Absolute links to our own domain are checked against the PR's copy.
        const target = internal ? url.replace(/^https?:\/\/(www\.)?alphageninsurance\.com/, `http://127.0.0.1:${port}`) : url;
        const status = await checkLink(page.request, target, !internal);
        if (typeof status === 'number' && status < 400) continue;
        if (!internal && BOT_WALL.has(status)) {
          notes.push(`\`${path}\`: ${url} answered ${status} to an automated request — check it by hand`);
        } else {
          fail(path, `broken link ${url} (${status})`);
        }
      }
    }
    await context.close();
  }
}
await browser.close();

const lines = [`### playwright: ${failures.length ? '**failed**' : '**passed**'}`, '',
  `Pages: ${pages.map((p) => '`' + p + '`').join(', ')} at desktop and 390px.`, ''];
lines.push(...failures.map((f) => `- ${f}`));
if (notes.length) lines.push('', '**Notes (not failures)**', ...notes.map((n) => `- ${n}`));
const text = lines.join('\n');
console.log(text);
if (process.env.GITHUB_STEP_SUMMARY) appendFileSync(process.env.GITHUB_STEP_SUMMARY, text + '\n');
process.exit(failures.length ? 1 : 0);
