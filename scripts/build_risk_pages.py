#!/usr/bin/env python3
"""Build AlphaGen's risk-type landing pages from data/risk-pages.json.

    python3 scripts/build_risk_pages.py          # build everything
    python3 scripts/build_risk_pages.py --check  # build in memory, fail if a file is stale

Writes:
  <slug>/index.html   one page per risk type (e.g. /workers-compensation-insurance-florida/)
  insurance/index.html  the hub, grouped Commercial / Personal
  sitemap.xml         the block between the RISK markers
  every page's nav    adds the "Coverage" link to nav.nav-links and nav.mobile-nav (idempotent)

Nothing is edited by hand except data/risk-pages.json. The header, footer and the
InsuranceAgency JSON-LD are copied from index.html, so the pages never drift from
the rest of the site. Standard library only; no build step on GitHub Pages.

Pricing rule (Bill, 2026-10-31): a page may show a historical premium range only
from data that Bill approved at GATE B2, inside its own "historically paid" section,
with the source named and linked in the text and the caveat directly under it.
validate() fails the build on any dollar figure anywhere else on the page.
"""
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "risk-pages.json"
HOME = ROOT / "index.html"
SITE = "https://alphageninsurance.com"
HUB_SLUG = "insurance"
SITEMAP_START, SITEMAP_END = "<!-- RISK:START -->", "<!-- RISK:END -->"
ASSET_VERSION = "20261101"
NAV_LABEL = "Coverage"

GROUPS = [("commercial", "Business insurance"), ("personal", "Home and personal insurance")]
BANNED_PRICE_WORDS = re.compile(
    r"as low as|from \$|starting at|\bsave\b|savings|cheapest|guarantee", re.I)
DOLLAR_RE = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?(?:\s?(?:k|K|million|billion))?")

e = html.escape


# --- shared site chrome, read from index.html --------------------------------

def site_parts(home=None):
    home = home if home is not None else HOME.read_text(encoding="utf-8")
    m = re.search(r'<script type="application/ld\+json">\s*\{\s*"@context": "https://schema.org",\s*'
                  r'"@type": "InsuranceAgency".*?</script>', home, re.S)
    if not m:
        sys.exit("InsuranceAgency JSON-LD not found in index.html")
    agency = m.group(0)
    header = re.search(r'<header class="site-header".*?</nav>\s*(?=<main)', home, re.S).group(0)
    footer = re.search(r'<footer class="site-footer">.*?</footer>', home, re.S).group(0)
    gtag = re.search(r"<!-- Google tag \(gtag\.js\).*?</script>\s*<script>.*?</script>", home, re.S).group(0)
    verify = re.search(r'<meta name="google-site-verification"[^>]*>', home).group(0)
    return {"agency": agency, "header": header.rstrip() + "\n", "footer": footer, "gtag": gtag,
            "verify": verify}


def url(slug):
    return f"{SITE}/{slug}/"


def jsonld_block(obj):
    return ('<script type="application/ld+json">\n'
            + json.dumps(obj, indent=2, ensure_ascii=False) + "\n</script>")


def faq_jsonld(page):
    return jsonld_block({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": f["q"],
                        "acceptedAnswer": {"@type": "Answer", "text": f["a_plain"]}}
                       for f in page["faqs"]],
    })


def crumbs_jsonld(page):
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"},
             {"@type": "ListItem", "position": 2, "name": NAV_LABEL, "item": url(HUB_SLUG)}]
    if page.get("slug") != HUB_SLUG:
        items.append({"@type": "ListItem", "position": 3, "name": page["h1"], "item": url(page["slug"])})
    return jsonld_block({"@context": "https://schema.org", "@type": "BreadcrumbList",
                         "itemListElement": items})


def head(page, parts, extra_jsonld):
    t, d, canon = e(page["title"]), e(page["description"]), url(page["slug"])
    og = page.get("og_image") or f"{SITE}/assets/img/alphagen-og.png"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{parts['gtag']}
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canon}">
<meta name="robots" content="index,follow">
{parts['verify']}
<meta property="og:site_name" content="AlphaGen Insurance Agency">
<meta property="og:type" content="website">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{e(og)}">
<meta property="og:locale" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{e(og)}">
<link rel="icon" type="image/png" href="/assets/img/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/site.css?v={ASSET_VERSION}">
<script defer src="/assets/js/site.js?v={ASSET_VERSION}"></script>
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
{parts['agency']}
{extra_jsonld}
</head>
<body>
{parts['header']}"""


# --- the form: the site's own .ag-form, with this page's line ----------------

LINE_FIELDS = {  # required fields per Worker line (01_AlphaGen/quote-api/worker.js LINES)
    "general-liability": {"company", "phone"},
    "workers-comp": {"company", "phone"},
    "commercial": {"company", "phone"},
    "cyber": {"company", "phone"},
    "homeowners": set(),
    "general-inquiry": set(),
}


def form(page, cfg, interest_options=None):
    line, fid = page["line"], page["slug"]
    req = LINE_FIELDS[line]
    star = '<span class="ag-req" aria-hidden="true">*</span>'
    personal = page.get("group") == "personal"

    def field(name, label, typ, auto, maxlen, extra=""):
        r = name in req or name in ("name", "email")
        return (f'    <div class="ag-field">\n'
                f'      <label for="ag-{fid}-{name}">{label}{star if r else ""}</label>\n'
                f'      <input id="ag-{fid}-{name}" name="{name}" type="{typ}"{" required" if r else ""} '
                f'autocomplete="{auto}" maxlength="{maxlen}"{extra}>\n    </div>\n')

    rows = [field("name", "Full name", "text", "name", 120, ' autocapitalize="words"')]
    if not personal:
        rows.append(field("company", "Company / business name", "text", "organization", 160))
    rows.append(field("email", "Email", "email", "email", 200, ' inputmode="email" spellcheck="false"'))
    rows.append(field("phone", "Phone", "tel", "tel", 40, ' inputmode="tel" placeholder="(561) 555-0100"'))
    risk = ""
    if interest_options:
        opts = "\n".join(f'        <option value="{e(o)}">{e(o)}</option>' for o in interest_options)
        risk = (f'    <div class="ag-field">\n'
                f'      <label for="ag-{fid}-interest">What do you need to insure?</label>\n'
                f'      <select id="ag-{fid}-interest" name="interest">\n'
                f'        <option value="">Choose one (optional)</option>\n{opts}\n'
                f'      </select>\n    </div>\n')
    else:
        risk = f'  <input type="hidden" name="risk" value="{e(page["risk_label"])}">\n'
    hidden_risk = risk if not interest_options else ""
    shown_risk = risk if interest_options else ""
    return f"""<form class="ag-form" method="POST" action="/api/quote" novalidate>
  <input type="hidden" name="line" value="{line}">
{hidden_risk}  <fieldset>
    <legend class="visually-hidden">{e(page.get('form_legend', 'Request an insurance quote'))}</legend>

{''.join(rows)}{shown_risk}
    <div class="ag-field">
      <label for="ag-{fid}-notes">Anything else we should know?</label>
      <textarea id="ag-{fid}-notes" name="notes" rows="4" maxlength="4000"></textarea>
      <p class="ag-hint">{e(page.get('form_hint', cfg['form_hint']))}</p>
    </div>

    <!-- Hidden from people and from screen readers. Bots fill it; the server then
         answers as though it succeeded and stores nothing. -->
    <div class="ag-hp" aria-hidden="true">
      <label for="ag-{fid}-website">Leave this field empty</label>
      <input id="ag-{fid}-website" name="website" type="text" tabindex="-1" autocomplete="off">
    </div>

    <div class="cf-turnstile" data-sitekey="0x4AAAAAAFJE_EDJ9yD3WxUQ" data-theme="light" data-appearance="interaction-only"></div>

    <button type="submit" class="btn btn-primary btn-block">{e(page.get('button', 'Request my quote'))}</button>

    <p class="ag-privacy">We use your details only to prepare your quote. See our
      <a href="/privacy-policy/">privacy policy</a>.</p>
  </fieldset>
</form>

<p class="form-help">Prefer to talk? Call <a href="tel:5612200402">(561) 220-0402</a> or email <a href="mailto:bill@alphageninsurance.com">bill@alphageninsurance.com</a></p>"""


# --- page sections ---------------------------------------------------------

def paras(items):
    return "\n".join(f"    <p>{p}</p>" for p in items)


def asks_section(page, cfg):
    groups = []
    for g in page["insurer_requests"]:
        lis = []
        for it in g["items"]:
            why = f' <span class="muted">— {it["why"]}</span>' if it.get("why") else ""
            lis.append(f"        <li>{it['text']}{why}</li>")
        groups.append(f'    <h3>{e(g["group"])}</h3>\n    <ul class="check-list">\n' + "\n".join(lis) + "\n    </ul>")
    forms = page.get("application_forms")
    forms_p = f"\n    <p class=\"small muted\">{forms}</p>" if forms else ""
    return (f'    <h2 id="what-insurers-ask">What insurers ask for</h2>\n'
            f"    <p>{cfg['asks_intro']}</p>\n" + "\n".join(groups) + forms_p +
            f"\n    <p>{cfg['asks_ready']}</p>")


def pricing_section(page, cfg):
    pr = page.get("pricing")
    if not pr:
        return ""
    heading = pr.get("heading") or ("What homeowners have historically paid" if page["group"] == "personal"
                                    else "What businesses have historically paid")
    figs = "\n".join(f"      <li>{f['text']} (<a href=\"{e(f['url'])}\" rel=\"nofollow\">{e(f['source'])}</a>, "
                     f"{e(f['period'])})</li>" for f in pr["figures"])
    return f"""    <h2 id="historical-pricing">{e(heading)}</h2>
    <div class="aside-box pricing-box">
    <p>{pr['summary']}</p>
    <ul>
{figs}
    </ul>
    <p class="small">Figures as of {e(pr['as_of'])}.</p>
    <p class="pricing-caveat">{pr['caveat']}</p>
    </div>"""


def faq_section(page):
    out = ['    <h2 id="faq">Questions we hear</h2>']
    for f in page["faqs"]:
        out.append(f'    <h3>{e(f["q"])}</h3>\n    <p>{f["a"]}</p>')
    return "\n".join(out)


def related_section(page, by_slug):
    links = []
    for r in page.get("related", []):
        if r.startswith("/"):
            label = page.get("related_labels", {}).get(r, r)
            links.append(f'      <li><a href="{r}">{label}</a></li>')
        else:
            p = by_slug[r]
            links.append(f'      <li><a href="/{p["slug"]}/">{e(p["h1"])}</a></li>')
    return ('    <h2 id="related">Related coverage</h2>\n    <ul>\n' + "\n".join(links) +
            f'\n      <li><a href="/{HUB_SLUG}/">All coverage we place</a></li>\n    </ul>')


def risk_page(page, cfg, by_slug, parts):
    body = f"""
<main id="main">
<section>
  <div class="container article">
    <p class="small"><a href="/">Home</a> &rsaquo; <a href="/{HUB_SLUG}/">{NAV_LABEL}</a> &rsaquo; {e(page['h1'])}</p>
    <h1>{e(page['h1'])}</h1>
    <p class="lead">{page['intro']}</p>
    <p>{cfg['agency_line']}</p>

    <h2 id="who">Who it's for</h2>
{paras(page['who'])}

    <h2 id="what-it-can-include">What it can include</h2>
    <ul>
{chr(10).join('      <li>' + i + '</li>' for i in page['includes'])}
    </ul>
    <p><strong>{cfg['coverage_caveat']}</strong></p>

{asks_section(page, cfg)}

{pricing_section(page, cfg)}

{faq_section(page)}

{related_section(page, by_slug)}

    <h2 id="quote">{e(page.get('form_heading', cfg['form_heading']))}</h2>
    <p>{cfg['form_intro']}</p>

{form(page, cfg)}
  </div>
</section>
</main>

"""
    jsonld = faq_jsonld(page) + "\n" + crumbs_jsonld(page)
    return head(page, parts, jsonld) + body + parts["footer"] + "\n</body>\n</html>\n"


def hub_page(data, parts):
    cfg, hub, pages = data["config"], data["hub"], data["pages"]
    sections = []
    for key, label in GROUPS:
        cards = []
        for p in [p for p in pages if p["group"] == key]:
            cards.append(f'      <a class="card" href="/{p["slug"]}/">\n        <h3>{e(p["card_title"])}</h3>\n'
                         f'        <p>{p["card_text"]}</p>\n      </a>')
        sections.append(f'    <h2 id="{key}">{e(label)}</h2>\n    <div class="grid grid-3">\n'
                        + "\n".join(cards) + "\n    </div>")
    local = "\n".join(f'      <li><a href="{u}">{l}</a></li>' for u, l in hub["local_pages"])
    page = dict(hub, slug=HUB_SLUG, line="general-inquiry", group="commercial")
    body = f"""
<main id="main">
<section>
  <div class="container">
    <h1>{e(hub['h1'])}</h1>
    <p class="lead">{hub['intro']}</p>
    <p>{cfg['agency_line']}</p>

{chr(10).join(sections)}

    <h2 id="local">Local pages</h2>
    <ul>
{local}
    </ul>
    <p>{hub['held_note']}</p>
    <p><strong>{cfg['coverage_caveat']}</strong></p>

    <div class="narrow">
    <h2 id="quote">{e(hub['form_heading'])}</h2>
    <p>{hub['form_intro']}</p>

{form(page, cfg, interest_options=[p['risk_label'] for p in pages] + ['Something else'])}
    </div>
  </div>
</section>
</main>

"""
    hub_faq = dict(page, faqs=hub["faqs"])
    jsonld = faq_jsonld(hub_faq) + "\n" + crumbs_jsonld(page)
    return head(page, parts, jsonld) + body + parts["footer"] + "\n</body>\n</html>\n"


def not_found_page(parts):
    """Branded 404 for GitHub Pages: routes a lost visitor to the hub and the general inquiry form."""
    page = {"slug": "404", "title": "Page not found | AlphaGen Insurance Agency",
            "description": "That page has moved or no longer exists. Browse the coverage AlphaGen places in Florida or send us a question."}
    h = head(page, parts, "").replace('<link rel="canonical" href="https://alphageninsurance.com/404/">\n', "")
    h = h.replace('<meta name="robots" content="index,follow">', '<meta name="robots" content="noindex,follow">')
    h = h.replace('<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>\n', "")
    h = re.sub(r'<meta property="og:url"[^>]*>\n', "", h)
    body = f"""
<main id="main">
<section>
  <div class="container narrow">
    <h1>We couldn't find that page</h1>
    <p class="lead">The page may have moved, or the link may be out of date.</p>
    <ul>
      <li><a href="/{HUB_SLUG}/">Browse the coverage we place in Florida</a></li>
      <li><a href="/general-inquiry/">Send us a question</a></li>
      <li><a href="/blog/">Read the blog</a></li>
      <li><a href="/">Go to the homepage</a></li>
    </ul>
    <p>Or call <a href="tel:5612200402">(561) 220-0402</a>.</p>
  </div>
</section>
</main>

"""
    return h + body + parts["footer"] + "\n</body>\n</html>\n"


# --- nav: add Coverage to every page that carries the site menu -------------

def add_nav(text):
    if f'<a href="/{HUB_SLUG}/">' in text:
        return text
    text = re.sub(r'(<nav class="nav-links"[^>]*>\s*<a href="/about-us/">About</a>\n)(\s*)',
                  lambda m: m.group(1) + m.group(2) + f'<a href="/{HUB_SLUG}/">{NAV_LABEL}</a>\n' + m.group(2),
                  text, count=1)
    text = re.sub(r'(<nav class="mobile-nav"[^>]*>\s*<a href="/about-us/">About</a>\n)(\s*)',
                  lambda m: m.group(1) + m.group(2) + f'<a href="/{HUB_SLUG}/">{NAV_LABEL}</a>\n' + m.group(2),
                  text, count=1)
    return text


def bump_assets(text):
    return re.sub(r'(/assets/(?:css/site\.css|js/site\.js))\?v=\d+', rf"\1?v={ASSET_VERSION}", text)


# --- sitemap ---------------------------------------------------------------

def sitemap_block(data):
    rows = [f"<url><loc>{url(HUB_SLUG)}</loc><lastmod>{data['hub']['last_reviewed']}</lastmod><priority>0.9</priority></url>"]
    for p in data["pages"]:
        rows.append(f"<url><loc>{url(p['slug'])}</loc><lastmod>{p['last_reviewed']}</lastmod>"
                    f"<priority>0.8</priority></url>")
    return SITEMAP_START + "\n" + "\n".join(rows) + "\n" + SITEMAP_END


def update_sitemap(text, data):
    block = sitemap_block(data)
    if SITEMAP_START in text:
        return re.sub(re.escape(SITEMAP_START) + r".*?" + re.escape(SITEMAP_END), lambda m: block, text, flags=re.S)
    return text.replace("</urlset>", block + "\n</urlset>")


# --- validation ------------------------------------------------------------

def visible(fragment):
    for tag in ("script", "style", "form"):
        fragment = re.sub(rf"<{tag}\b.*?</{tag}\s*>", " ", fragment, flags=re.S | re.I)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


def validate(data, built):
    errs = []
    slugs = [p["slug"] for p in data["pages"]]
    if len(set(slugs)) != len(slugs):
        errs.append("duplicate slugs")
    titles = [p["title"] for p in data["pages"]] + [data["hub"]["title"]]
    if len(set(titles)) != len(titles):
        errs.append("duplicate titles")
    for p in data["pages"] + [dict(data["hub"], slug=HUB_SLUG)]:
        if len(p["title"]) > 60:
            errs.append(f"{p['slug']}: title {len(p['title'])} chars > 60")
        if len(p["description"]) > 155:
            errs.append(f"{p['slug']}: description {len(p['description'])} chars > 155")
        for field in ("title", "description", "h1"):
            if DOLLAR_RE.search(p.get(field, "")) or "%" in p.get(field, ""):
                errs.append(f"{p['slug']}: a price or rate in {field}")
    for p in data["pages"]:
        if p["line"] not in LINE_FIELDS:
            errs.append(f"{p['slug']}: line {p['line']} is not a Worker line")
        if not 4 <= len(p["faqs"]) <= 6:
            errs.append(f"{p['slug']}: needs 4-6 FAQs")
        page_html = built[f"{p['slug']}/index.html"]
        main = re.search(r"<main\b.*?</main>", page_html, re.S).group(0)
        pr = p.get("pricing")
        price_html = ""
        if pr:
            m = re.search(r'<h2 id="historical-pricing">.*?</div>', main, re.S)
            price_html = m.group(0) if m else ""
            if pr["caveat"] not in price_html:
                errs.append(f"{p['slug']}: caveat missing from the pricing section")
            for f in pr["figures"]:
                for k in ("text", "source", "period", "basis", "url"):
                    if not f.get(k):
                        errs.append(f"{p['slug']}: pricing figure missing {k}")
                if f["source"] not in html.unescape(price_html) or f["url"] not in html.unescape(price_html):
                    errs.append(f"{p['slug']}: figure source not named and linked in the text")
            if not pr.get("approved_gate_b2"):
                errs.append(f"{p['slug']}: pricing not marked approved at GATE B2")
        outside = main.replace(price_html, " ") if price_html else main
        # The FAQ may repeat an approved range only when it names the same source.
        for f in p["faqs"]:
            for d in DOLLAR_RE.findall(f["a"]):
                if not pr or not any(d in fig["text"] for fig in pr["figures"]):
                    errs.append(f"{p['slug']}: FAQ dollar figure {d} is not an approved pricing figure")
            outside = outside.replace(f["a"], " ")
        stray = DOLLAR_RE.findall(visible(outside))
        if stray:
            errs.append(f"{p['slug']}: dollar figures outside the pricing block: {stray}")
        if BANNED_PRICE_WORDS.search(visible(main)):
            errs.append(f"{p['slug']}: banned price wording: {BANNED_PRICE_WORDS.search(visible(main)).group(0)}")
        head_part = page_html.split("</head>")[0]
        if DOLLAR_RE.search(re.sub(r"<script.*?</script>", "", head_part, flags=re.S)):
            errs.append(f"{p['slug']}: dollar figure in <head> (title/meta/OG)")
        for js in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page_html, re.S):
            if re.search(r'"(Offer|PriceSpecification|priceRange|price)"', js) or DOLLAR_RE.search(js):
                errs.append(f"{p['slug']}: price markup or figure in JSON-LD")
        for term in ("3333692", "savingsre", "GTM-K4HVBNM", "your policy covers"):
            if term.lower() in page_html.lower():
                errs.append(f"{p['slug']}: banned term {term}")
    return errs


# --- main ------------------------------------------------------------------

def build(data, home=None):
    parts = site_parts(home)
    by_slug = {p["slug"]: p for p in data["pages"]}
    out = {}
    for p in data["pages"]:
        out[f"{p['slug']}/index.html"] = risk_page(p, data["config"], by_slug, parts)
    out[f"{HUB_SLUG}/index.html"] = hub_page(data, parts)
    out["404.html"] = not_found_page(parts)
    out["email-templates/agile/risk-links-block.html"] = email_block(data)
    return out


def email_block(data, campaign="ins-monthly"):
    """Paste-in block for the INS monthly Agile emails. House UTM format:
    utm_source=agilecrm&utm_medium=email&utm_campaign=<name>&utm_content=<slug>.
    Change utm_campaign to the campaign the block is pasted into."""
    rows = []
    for key, label in GROUPS:
        links = [f'<li style="margin:0 0 6px 0;"><a href="{SITE}/{p["slug"]}/?utm_source=agilecrm&amp;utm_medium=email'
                 f'&amp;utm_campaign={campaign}&amp;utm_content={p["slug"]}" style="color:#082F72;">{e(p["card_title"])}</a></li>'
                 for p in data["pages"] if p["group"] == key]
        rows.append(f'<p style="margin:12px 0 6px 0;font-weight:bold;">{e(label)}</p>\n<ul style="margin:0;padding-left:18px;">\n'
                    + "\n".join(links) + "\n</ul>")
    return ("<!-- AlphaGen risk-page links for Agile CRM emails. Generated by scripts/build_risk_pages.py; "
            "do not edit by hand. Set utm_campaign to the sending campaign. -->\n"
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.5;color:#1b2a3a;">\n'
            f'<p style="margin:0 0 6px 0;">Coverage we place in Florida, with what insurers ask for to quote it: '
            f'<a href="{SITE}/{HUB_SLUG}/?utm_source=agilecrm&amp;utm_medium=email&amp;utm_campaign={campaign}&amp;utm_content={HUB_SLUG}" style="color:#082F72;">see all</a></p>\n'
            + "\n".join(rows) + "\n</div>\n")


def main():
    check = "--check" in sys.argv
    data = json.loads(DATA.read_text(encoding="utf-8"))
    # Nav first, on index.html too, so the header copied into new pages has it.
    nav_changes = {}
    for f in sorted(ROOT.rglob("*.html")):
        if ".git" in f.parts or "node_modules" in f.parts:
            continue
        rel = f.relative_to(ROOT).as_posix()
        if rel.startswith(("scripts/", "email-templates/", "data/")):
            continue
        t = f.read_text(encoding="utf-8")
        n = bump_assets(add_nav(t)) if 'class="nav-links"' in t or "/assets/" in t else t
        if n != t:
            nav_changes[rel] = n
    built = build(data, nav_changes.get("index.html"))
    errs = validate(data, built)
    if errs:
        print("Validation failed:\n  " + "\n  ".join(errs))
        sys.exit(1)
    if not check:
        for rel, t in nav_changes.items():
            (ROOT / rel).write_text(t, encoding="utf-8", newline="\n")
    sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    built["sitemap.xml"] = update_sitemap(sm, data)
    stale = []
    for rel, text in built.items():
        path = ROOT / rel
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                stale.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
    if check:
        stale += list(nav_changes)
        if stale:
            print("Stale (run without --check):\n  " + "\n  ".join(stale))
            sys.exit(1)
        print(f"OK: {len(built) - 1} pages and the sitemap are current.")
    else:
        print(f"Built {len(built) - 1} pages, updated the sitemap and {len(nav_changes)} page menus.")


if __name__ == "__main__":
    main()
