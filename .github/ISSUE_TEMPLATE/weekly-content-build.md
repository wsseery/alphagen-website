---
name: Weekly content build
about: Filed by the Monday automation. Carries one blog post and one class-by-city page for the Claude workflow to build.
title: "Weekly content build: week NN, CLASS, CITY"
labels: []
---

<!--
HOW THIS TEMPLATE WORKS

The Claude workflow starts when an issue is OPENED with the at-mention in its
body. This template deliberately does not contain that mention anywhere, so a
blank or half-filled issue opened from it starts nothing.

The automation fills every {{PLACEHOLDER}} and, last, replaces {{MENTION}} in
section 6 with the at-mention. That one replacement is what starts the run.
Filing by hand: fill everything, then replace {{MENTION}} yourself.

GitHub Actions cannot read Google Drive, so the full content travels in this
issue body. Do not link to Drive files instead of pasting them.
-->

## 1. Target

- **Week:** {{WEEK}}
- **Class:** {{CLASS}}
- **City:** {{CITY}}
- **Line:** {{LINE}}

## 2. Output paths

- **Blog post:** `blog/{{BLOG_SLUG}}/index.html`
- **Class-by-city page:** `{{LANDING_SLUG}}/index.html`

## 3. CTA target

`{{CTA_TARGET}}`

One CTA per page, to this specific quote form. Never `/get-a-quote/`.

## 4. Sourced figures

These are the only numbers that may appear on either page. Each carries its source link inline.

| # | Figure | Source | Link |
|---|---|---|---|
| 1 | {{FIGURE_1}} | {{SOURCE_1}} | {{LINK_1}} |
| 2 | {{FIGURE_2}} | {{SOURCE_2}} | {{LINK_2}} |
| 3 | {{FIGURE_3}} | {{SOURCE_3}} | {{LINK_3}} |

## 5. Content

Use the copy exactly as written. It has been through a compliance pass: reword nothing, add no statistic, drop no disclaimer.

### 5a. Blog post

{{BLOG_MARKDOWN}}

### 5b. Class-by-city page

{{LANDING_MARKDOWN}}

## 6. Build instruction

{{MENTION}} build the two pages in section 2 from the content in section 5, following `2026-09-30_alphagen_doc_claude-code-blog-build-prompt_v01.md`. That document is not readable from here, so its steps are restated below. Read this repo's `CLAUDE.md` first.

**Build**

- Match the existing page pattern exactly: same stylesheet, same header and footer markup, same GA4 `G-RG0E11KB0Q` gtag.js block, root-relative links, no build step.
- `<title>` and `<meta name="description">` come from each file's SEO-fields table, not the H1. Add `og:title`, `og:description`, `og:url` and `og:image`.
- Blog post: H1 and H2s as in the copy, in order. Source links are external, `rel="nofollow"`, same tab. Exactly one CTA, at the end, to the CTA target in section 3.
- Class-by-city page: reuse the native quote form for the line in section 1, copied from that line's quote page, with the same hidden `line` value. That form is the page's only CTA. Copy the `InsuranceAgency` JSON-LD block from `index.html` verbatim, and copy the `<head>` scripts and stylesheet links from that line's quote page verbatim. Any script, form or schema block that is not an exact copy of one already on the site makes the PR a code PR, and Bill has to merge it.
- Address is "5550 Glades Road, Boca Raton" with no suite number.
- OG image: if this issue carries an "OG IMAGES" section, generate the card with its `make_og.py` from the repo root, commit only the JPEG, and put the script's "Font face in use" line in the PR body. Without that section, keep the `og:image` tag and say in the PR body that the file is missing; never make a placeholder.
- Phone is always (561) 220-0402, whatever number the copy carries.

**Working rules for this run** (see `CLAUDE.md`, "Weekly content builds")

- Stay in the repo root. Never `cd`, never create a working folder.
- Commit and push as soon as the files exist, with plain `git add` / `git commit` / `git push`. Check after pushing.

**Wire in**

- Add both URLs to `sitemap.xml`.
- Add the post to `blog/index.html`, newest first.
- Add the class-by-city page wherever the commercial section lists class pages.

**Check before opening the PR**

Search both new files and fix any hit in the page body (the shared header and footer link to `/get-a-quote/` on every page and are not a hit):

```
get-a-quote
3333692
your policy covers
save up to
starting at
fully protected
dialridge
savingsre
```

Confirm each new page has exactly one CTA, carries licence G164863, and carries the footer insurance disclaimer block used site-wide. Confirm every number on both pages is one of the figures in section 4, with its source link. Any other number in the copy is an illustrative example: leave it as written and add it to the table as "Illustrative example — not a statistic".

**Post the PR body, do not merge**

You cannot open the PR yourself. Push the branch and post the full PR body in your final comment; Claude Code or Bill opens the PR, which starts the required checks. The PR body states both new URLs, the CTA target on each, and the OG image status. It must also carry a `## Sourced figures` heading followed by the table from section 4, keeping its `Figure` and `Source` columns, plus a row for every illustrative example. The `content-rules` check reads numbers from both columns, and any number on a page that is not in the table fails the check.

Change only the two new pages, `sitemap.xml` and `blog/index.html`, plus copy inside `<main>` on the page that lists class pages. Do not merge it yourself. A PR that changes only content merges itself once every required check passes (GLOBAL_INSTRUCTIONS §8a). Anything else waits for Bill — and a new JSON-LD block (FAQPage, BlogPosting) not already on the site counts as a schema change, so a post that carries one is a code PR.
