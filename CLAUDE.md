# CLAUDE.md — alphagen-website

Repo-local facts only. Everything else lives in
`G:\My Drive\Claude\BillSeery\00_Global\GLOBAL_INSTRUCTIONS.md` (ventures, naming, compliance)
and `RUNBOOK_MENU.md` (procedures). **Do not copy those files here — pointers only.**

Venture `01_AlphaGen` — AlphaGen Insurance Agency. Target: **alphageninsurance.com** via GitHub
Pages. Rebuilt from WordPress/Bluehost in Sep 2026 on the same stack as `savingsre-website`.

## ⛔ This repo is PUBLIC

- **No client data, ever.** No client names, policy numbers, DOBs, SSNs, carrier submission data,
  loss runs, dec pages or financial account numbers. Client material stays in
  `01_AlphaGen/clients/` on Drive, which is confidential by default.
- Never commit mailbox exports, form submissions, or anything from `%USERPROFILE%\Downloads`.

## Compliance

- **Insurance content only.** Never mix ventures — nothing here may imply real-estate advice,
  link to real-estate listings, or touch DialRidge product claims. savingsre.com may appear in
  exactly three places: the two real-estate redirect stubs, and the single "See our affiliate
  site" cross-marketing link on `/relocation-and-insurance-guide/` (restored 2026-09-28 at Bill's
  direction). No other real-estate links, listings or documents. The relocation guide PDF that
  gate delivers is hosted on savingsre.com, not here.
- FL insurance licence **G164863** (2-20 General Lines) is the **only** licence that may appear
  on this site. **Never cite 3333692** (the real-estate licence) anywhere in this repo.
- Every page footer carries the Insurance block from `00_Global/LEGAL_DISCLAIMERS.md`, verbatim.
- **Never fabricate** figures, carrier counts, years in business, policy counts, or client names.
  The four homepage statistics were cut on 2026-09-27 at Bill's direction; do not reintroduce
  them or any replacement numbers without a verified source.
- Analytics is GA4 `G-RG0E11KB0Q` via gtag.js in `<head>` of every page. **Never** SavingsRE's
  `GTM-K4HVBNM`. Do not add a Google Ads tag — the imported conversion would double-count.

## Structure

- WordPress URLs are preserved byte-for-byte: `<slug>/index.html` is served at `/<slug>/`.
  Links are root-relative (`/about-us/`). Do not rename or flatten these paths.
- One stylesheet `assets/css/site.css`, one script `assets/js/site.js`. No framework, no build
  step, no node_modules. Header and footer are plain markup repeated in every page.
- Quote pages carry the native `.ag-form` (2026-09-29), posting to `/api/quote` — a Cloudflare Worker
  guarded by Turnstile — with a hidden `line` value per form (ten forms on nine pages; the relocation
  page has a personal and a business form). The submit handler lives in `assets/js/site.js` and uses
  `window.agTrack`. The `/thank-you/` page keeps its `?line=` handling and fires `generate_lead` only
  when the URL lacks `src=ag`, because the form already fired it on submit — change one end without the
  other and every lead double-counts. The two ebook gates still use their JotForm embeds.
- `redirects.csv` is the Cloudflare Bulk Redirects import; each old path also has a meta-refresh
  stub so redirects work before the Cloudflare list is enabled.
- **No `CNAME` file until cutover.** Adding it (and enabling the Pages custom domain) is Bill's
  step in the migration plan, Phase 6.

## Conventions

- **LF line endings.** `.gitattributes` (`* text=auto eol=lf`). If a diff shows every file
  modified with symmetric insert/delete counts, run `git diff --ignore-all-space`; if empty, it
  is line-ending churn, not a change.
- **GitHub Pages lags** 30–90 s behind a commit. Verify against
  `raw.githubusercontent.com/wsseery/alphagen-website/main/<path>?t=<ts>` first.
- Blog posts live at `blog/<slug>/index.html` and are listed by hand in `blog/index.html` and
  `sitemap.xml`.

## Working agreement

Draft, do not ship. Commits, pushes and PRs are fine without asking. **Merging to `main` is a
release.** Who may merge is set by GLOBAL_INSTRUCTIONS §8a: a content-only PR merges itself once
its required checks pass; every other PR needs Bill's explicit "ship it." Never merge by hand,
never use `--admin`. Never touch DNS, Cloudflare, Bluehost, JotForm or Google accounts from here.

The §8a gate is `.github/workflows/content-automerge.yml` (classification and the auto-merge
switch), `content-gate.yml` (`playwright`, `compliance-grep`) and `content-rules.yml`, with the
logic in `.github/checks/`. `python .github/checks/classify.py --git main HEAD` shows how a branch
would be classified.
