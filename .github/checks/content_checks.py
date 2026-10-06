"""compliance-grep and content-rules: two required checks on every PR.

  content_checks.py grep  <base-sha>   banned terms in what this PR adds
  content_checks.py rules <base-sha>   one CTA, disclaimer, sourced figures

Both compare the PR's checkout (HEAD) against <base-sha> and look only at what
the PR changes, so a pre-existing line elsewhere on the site never blocks an
unrelated PR. Both exit non-zero on any finding, with every finding listed.

The PR body (for the sourced-figures table) comes from $PR_BODY.
"""

import os
import re
import subprocess
import sys

import sitelib as S


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def changed(base):
    out = run(["git", "diff", "--name-status", "--no-renames", base, "HEAD"])
    rows = []
    for line in out.splitlines():
        status, path = line.split("\t", 1)
        if status[0] != "D":
            rows.append((status[0], path))
    return rows


def base_text(base, path):
    try:
        return run(["git", "show", f"{base}:{path}"])
    except subprocess.CalledProcessError:
        return None


def head_text(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (UnicodeDecodeError, FileNotFoundError):
        return None


# --- compliance-grep ------------------------------------------------------

# From the AlphaGen blog build prompt (2026-09-30) and the weekly issue
# template. Mirrored by hand: change the prompt and this list together.
BANNED = [
    "3333692",
    "your policy covers",
    "save up to",
    "starting at",
    "fully protected",
    "dialridge",
    "savingsre",
    "GTM-K4HVBNM",
]
# get-a-quote is checked inside <main> only: the shared header and footer link
# to it on every page, by design.

# CLAUDE.md: savingsre.com may appear on the two real-estate redirect stubs and
# the relocation guide page (plus the thank-you page that delivers its PDF).
SAVINGSRE_ALLOWED = {
    "real-estate-services-for-investors-and-relocation-assistance/index.html",
    "archive-real-estate-services-for-investors-and-relocation-assistance/index.html",
    "relocation-and-insurance-guide/index.html",
    "thank-you/index.html",
    "redirects.csv",
}

TEXT_EXT = re.compile(r"\.(html?|xml|txt|csv|json|md|svg|js|css)$", re.I)


def grep(base):
    findings = []
    for _, path in changed(base):
        if path.startswith(".github/") or not TEXT_EXT.search(path):
            continue
        head = head_text(path)
        if head is None:
            continue
        before = base_text(base, path) or ""
        for term in BANNED:
            if term == "savingsre" and path in SAVINGSRE_ALLOWED:
                continue
            rx = re.compile(re.escape(term), re.I)
            added = len(rx.findall(head)) - len(rx.findall(before))
            if added > 0:
                findings.append(f"`{path}`: adds `{term}` ({added}x)")
        if path.endswith(".html"):
            added = (len(S.GET_A_QUOTE_RE.findall(S.split_main(head)[0]))
                     - len(S.GET_A_QUOTE_RE.findall(S.split_main(before)[0])))
            if added > 0:
                findings.append(f"`{path}`: adds a `/get-a-quote/` link inside <main> "
                                "(the CTA must go to a specific quote form)")
    return findings


# --- content-rules --------------------------------------------------------

def sourced_figures(body):
    """Figures listed in the PR body's 'Sourced figures' table."""
    lines = (body or "").splitlines()
    start = next((i for i, l in enumerate(lines)
                  if re.match(r"\s*(#+|\*\*)\s*(\d+\.\s*)?sourced figures", l, re.I)), None)
    if start is None:
        return set(), False
    table = []
    for l in lines[start + 1:]:
        if l.strip().startswith("|"):
            table.append([c.strip() for c in l.strip().strip("|").split("|")])
        elif table:
            break
    if not table:
        return set(), False
    header = [c.lower() for c in table[0]]
    # Figure AND Source: a statute or CFR section cited on the page
    # ("§440.02(17)(b)", "49 C.F.R. part 387") is the source of a figure, and it
    # lives in the Source column. Reading Figure alone failed Week 04 (#20) on
    # every citation. Link and Used-in columns stay out.
    cols = ([i for i, h in enumerate(header) if "figure" in h or "source" in h]
            or range(1, len(header)))
    figs = set()
    for row in table[2:]:  # skip header and the |---| row
        for i in cols:
            if i < len(row):
                figs.update(S.numbers_in(row[i]))
    return figs, True


def site_facts(base):
    """Numbers the site already shows in its shared header and footer (address,
    phone, hours, licence): fair to repeat, not new figures."""
    home = base_text(base, "index.html") or ""
    return set(S.numbers_in(S.visible_text(S.split_main(home)[1])))


def rules(base, body):
    findings = []
    allowed, have_table = sourced_figures(body)
    facts = site_facts(base)

    for status, path in changed(base):
        kind = S.page_kind(path)
        if kind not in ("blog-post", "page", "blog-index"):
            continue
        head = head_text(path) or ""
        main = S.split_main(head)[0]
        new = status == "A"

        if new:
            found = S.ctas(main)
            if len(found) != 1:
                listed = "; ".join(found) or "none"
                findings.append(f"`{path}`: {len(found)} calls to action in <main>, "
                                f"need exactly 1 ({listed})")
            if S.norm(S.INSURANCE_DISCLAIMER) not in S.visible_text(head):
                findings.append(f"`{path}`: the Insurance disclaimer block is missing "
                                "or not verbatim")
            if "G164863" not in head:
                findings.append(f"`{path}`: licence G164863 is missing")

        # Indexes list posts by date; their numbers are not claims.
        if kind == "blog-index":
            continue
        before = set() if new else set(S.numbers_in(
            S.visible_text(S.split_main(base_text(base, path) or "")[0])))
        unsourced = sorted({n for n in S.numbers_in(S.visible_text(main))
                            if n not in before and n not in allowed
                            and n not in facts and not S.is_year(n)})
        if unsourced:
            where = ("" if have_table else
                     " (the PR body has no 'Sourced figures' table)")
            findings.append(f"`{path}`: figures not in this PR's sourced-figures table"
                            f"{where}: {', '.join(unsourced)}")
    return findings


def report(name, findings, ok_line):
    lines = [f"### {name}: " + ("**failed**" if findings else "**passed**"), ""]
    lines += [f"- {f}" for f in findings] or [ok_line]
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")
    return 1 if findings else 0


def main():
    mode, base = sys.argv[1], sys.argv[2]
    if mode == "grep":
        sys.exit(report("compliance-grep", grep(base),
                        "No banned term added by this PR."))
    if mode == "rules":
        sys.exit(report("content-rules", rules(base, os.environ.get("PR_BODY", "")),
                        "Every new page has one CTA and the disclaimer; "
                        "every new figure is sourced."))
    sys.exit(f"unknown mode {mode}")


if __name__ == "__main__":
    main()
