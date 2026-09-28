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
  link to real-estate listings, or touch DialRidge product claims. The two old real-estate URLs
  301 to savingsre.com and that is the only place that domain may appear.
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
- Quote pages embed JotForm iframes copied verbatim from the WordPress export (form ID in each iframe id);
  the `/thank-you/` page must keep its `?line=` handling and the `generate_lead` push.
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

Draft, do not ship. Commits, pushes and PRs are fine without asking; **merging to `main` is a
release and needs Bill's explicit "ship it."** Never touch DNS, Cloudflare, Bluehost, JotForm or
Google accounts from here.
