"""Shared helpers for the content gate: path classification and HTML inspection.

The rules implemented here are GLOBAL_INSTRUCTIONS.md §8a (merge authority split
by what the PR changes). That file lives on G:\\My Drive\\ and cannot be read
from an Actions runner, so the lists below are a hand-kept mirror of it.
If this file and §8a ever disagree, §8a wins and this file is the bug: change
§8a first, then here.

Pure standard library, so it runs on a bare runner with no install step.
"""

import html
import re

# --- §8a path lists -------------------------------------------------------

# Code: any one of these makes the whole PR a code PR. Checked FIRST.
CODE_PATTERNS = [
    (r"^\.github/", "anything under .github/"),
    (r"\.(js|mjs|cjs|ts|tsx|jsx|py|rb|go|sh|bash|ps1|php|pl)$", "executable source"),
    (r"^assets/css/", "shared stylesheet"),
    (r"^assets/js/", "shared script"),
    (r"\.css$", "stylesheet"),
    (r"(^|/)(CNAME|_config[^/]*|robots\.txt|_redirects|_headers|redirects\.csv)$",
     "build, deploy or redirect configuration"),
    (r"(^|/)(netlify\.toml|wrangler\.toml|vercel\.json)$", "deploy configuration"),
    (r"(^|/)(package(-lock)?\.json|yarn\.lock|pnpm-lock\.yaml|requirements[^/]*\.txt|"
     r"Pipfile(\.lock)?|Gemfile(\.lock)?|go\.(mod|sum))$", "dependency or lockfile"),
    (r"(^|/)clients/", "client material"),
    (r"(^|/)\.(gitattributes|gitignore|env[^/]*)$", "repository configuration"),
    (r"\.svg$", "SVG (can carry script)"),
]

# Content: a page or index the site serves. Checked SECOND; a path matching
# neither list is code (fail closed).
CONTENT_IMAGE = re.compile(r"^assets/img/[^/]+\.(png|jpe?g|webp|gif|avif)$", re.I)
BLOG_INDEX = "blog/index.html"
SITEMAP = "sitemap.xml"
BLOG_POST = re.compile(r"^blog/[a-z0-9][a-z0-9-]*/index\.html$")
ROOT_PAGE = re.compile(r"^[a-z0-9][a-z0-9-]*/index\.html$")
HOMEPAGE = "index.html"


def code_reason(path):
    for pattern, why in CODE_PATTERNS:
        if re.search(pattern, path, re.I):
            return why
    return None


def page_kind(path):
    """Which content allowlist entry a path matches, or None."""
    if path == SITEMAP:
        return "sitemap"
    if path == BLOG_INDEX:
        return "blog-index"
    if BLOG_POST.match(path):
        return "blog-post"
    if path == HOMEPAGE or ROOT_PAGE.match(path):
        return "page"
    if CONTENT_IMAGE.match(path):
        return "image"
    return None


def is_page(path):
    return page_kind(path) in ("blog-post", "page", "blog-index")


def url_for(path):
    if path == "index.html":
        return "/"
    if path.endswith("/index.html"):
        return "/" + path[: -len("index.html")]
    return "/" + path


# --- HTML inspection ------------------------------------------------------

MAIN_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.S | re.I)


def split_main(text):
    """(inside <main>, everything outside it). No <main> -> ('', text)."""
    m = MAIN_RE.search(text)
    if not m:
        return "", text
    return m.group(1), text[: m.start()] + "<main></main>" + text[m.end():]


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


# Anything that executes, tracks, loads, submits, redirects or carries schema.
# §8a makes analytics, tracking, schema-block and form-embed changes code, so a
# content page may only carry these if each one is a verbatim copy of a block
# the site already serves on main.
ACTIVE_BLOCK_RES = [
    re.compile(r"<script\b[^>]*>.*?</script\s*>", re.S | re.I),
    re.compile(r"<form\b.*?</form\s*>", re.S | re.I),
    re.compile(r"<style\b[^>]*>.*?</style\s*>", re.S | re.I),
    re.compile(r"<noscript\b[^>]*>.*?</noscript\s*>", re.S | re.I),
    re.compile(r"<iframe\b.*?(?:</iframe\s*>|/>)", re.S | re.I),
    re.compile(r"<(?:object|embed|base|portal)\b[^>]*>", re.I),
    re.compile(r"<meta\b[^>]*http-equiv[^>]*>", re.I),
    re.compile(r"<link\b[^>]*\brel=[\"']?(?:stylesheet|preload|modulepreload|prefetch|"
               r"preconnect|dns-prefetch|manifest|import)[^>]*>", re.I),
    # Any tag carrying an inline event handler or a javascript: URL.
    re.compile(r"<[a-z][^>]*\s(?:on[a-z]+\s*=|href\s*=\s*[\"']?\s*javascript:)[^>]*>", re.I),
]


def active_blocks(text):
    # Forms are matched whole first, then removed, so the inputs inside a
    # verbatim form are not re-checked one tag at a time.
    found = []
    for rx in ACTIVE_BLOCK_RES:
        for m in rx.finditer(text):
            found.append(norm(m.group(0)))
        if rx.pattern.startswith("<form"):
            text = rx.sub(" ", text)
    return found


def visible_text(fragment):
    for tag in ("script", "style", "form", "noscript"):
        fragment = re.sub(rf"<{tag}\b.*?</{tag}\s*>", " ", fragment, flags=re.S | re.I)
    fragment = re.sub(r"<!--.*?-->", " ", fragment, flags=re.S)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return norm(html.unescape(fragment))


# A figure is any run of digits, with optional $, thousands commas, decimals, %.
NUMBER_RE = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?")


def numbers_in(text):
    out = []
    for tok in NUMBER_RE.findall(text):
        core = tok.replace("$", "").replace(",", "").rstrip("%").rstrip(".")
        if core:
            out.append(core)
    return out


def is_year(core):
    return re.fullmatch(r"(19[9]\d|20\d\d)", core) is not None


# --- CTAs -----------------------------------------------------------------

ANCHOR_RE = re.compile(r"<a\b([^>]*)>", re.I)
HREF_RE = re.compile(r"href\s*=\s*[\"']([^\"']*)[\"']", re.I)
QUOTE_PATH_RE = re.compile(r"^(?:https?://(?:www\.)?alphageninsurance\.com)?"
                           r"/(?:[a-z0-9-]+-quote|get-a-quote|general-inquiry)/", re.I)


def ctas(main_html):
    """Calls to action inside <main>: native quote forms, links to a quote
    page, and anything marked as a button or CTA."""
    found = []
    for m in re.finditer(r"<form\b[^>]*>", main_html, re.I):
        found.append("form " + norm(m.group(0))[:80])
    without_forms = re.sub(r"<form\b.*?</form\s*>", " ", main_html, flags=re.S | re.I)
    for m in ANCHOR_RE.finditer(without_forms):
        attrs = m.group(1)
        href = HREF_RE.search(attrs)
        href = href.group(1) if href else ""
        if (QUOTE_PATH_RE.match(href) or "data-cta" in attrs
                or re.search(r"class\s*=\s*[\"'][^\"']*\bbtn\b", attrs)):
            found.append("link " + href)
    return found


GET_A_QUOTE_RE = re.compile(r"get-a-quote", re.I)

# Insurance block, verbatim from 00_Global/LEGAL_DISCLAIMERS.md (mirrored by
# hand, 2026-10-04). Compared after whitespace normalisation.
INSURANCE_DISCLAIMER = (
    "AlphaGen Insurance Agency is licensed in the State of Florida (2-20 General "
    "Lines, License G164863). This content is for general informational purposes "
    "only and is not a contract of insurance. Coverage is subject to eligibility, "
    "underwriting, and the terms, conditions, and exclusions of the issued policy. "
    "Rates and availability vary by state and are subject to change."
)
