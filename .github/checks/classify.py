"""content-classification: is this PR content-only, or code?

GLOBAL_INSTRUCTIONS.md §8a. A PR is content only when EVERY changed file is
content and NONE is code. A mixed PR is code. A path matching neither list is
code. Anything this script cannot decide is code. It never merges anything.

Two ways to run it:

  CI (pull_request_target):  classify.py --pr <number>
      Reads the PR's file list and the head versions of changed pages through
      the GitHub API. Nothing from the PR branch is checked out or executed;
      the "before" versions come from the base checkout this runs in.

  Locally, for testing:      classify.py --git <base-ref> <head-ref>

Writes a Markdown summary to $GITHUB_STEP_SUMMARY when set, and prints
`verdict=content` or `verdict=code` as its last line.
"""

import argparse
import base64
import glob
import json
import os
import subprocess

import sitelib as S


# --- sources --------------------------------------------------------------

def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


class GitSource:
    def __init__(self, base, head):
        self.base, self.head = base, head

    def files(self):
        out = run(["git", "diff", "--name-status", "-M", self.base, self.head])
        files = []
        for line in out.splitlines():
            parts = line.split("\t")
            status = {"A": "added", "M": "modified", "D": "removed",
                      "R": "renamed", "C": "copied", "T": "changed"}.get(parts[0][0], "changed")
            files.append({"filename": parts[-1], "status": status,
                          "previous_filename": parts[1] if len(parts) == 3 else None})
        return files

    def head_text(self, path):
        return run(["git", "show", f"{self.head}:{path}"])

    def base_text(self, path):
        try:
            return run(["git", "show", f"{self.base}:{path}"])
        except subprocess.CalledProcessError:
            return None

    def base_html_corpus(self):
        names = run(["git", "ls-tree", "-r", "--name-only", self.base]).split()
        return [self.base_text(n) or "" for n in names if n.endswith(".html")]


class ApiSource:
    """Head content over the API; base content from the base checkout."""

    def __init__(self, repo, number, head_sha):
        self.repo, self.number, self.head_sha = repo, number, head_sha

    def files(self):
        out = run(["gh", "api", "--paginate",
                   f"repos/{self.repo}/pulls/{self.number}/files?per_page=100",
                   "--jq", ".[] | {filename, status, previous_filename}"])
        files = [json.loads(line) for line in out.splitlines() if line.strip()]
        # The files endpoint stops at 3000 entries. Past that the list is
        # incomplete, and an incomplete list cannot prove a PR is content-only.
        if len(files) >= 3000:
            raise RuntimeError("PR has 3000+ files; the API list is truncated")
        return files

    def head_text(self, path):
        out = run(["gh", "api", f"repos/{self.repo}/contents/{path}?ref={self.head_sha}",
                   "--jq", ".content"])
        return base64.b64decode(out).decode("utf-8")

    def base_text(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return None

    def base_html_corpus(self):
        out = []
        for p in glob.glob("**/*.html", recursive=True):
            if p.replace("\\", "/").startswith(".github/"):
                continue
            with open(p, encoding="utf-8") as f:
                out.append(f.read())
        return out


# --- classification -------------------------------------------------------

def classify(src):
    files = src.files()
    if not files:
        return "code", [("(none)", "code", "PR has no changed files")]

    corpus = set()
    for text in src.base_html_corpus():
        corpus.update(S.active_blocks(text))

    rows = []  # (path, verdict, why)
    for f in files:
        path, status = f["filename"], f["status"]

        why = S.code_reason(path)
        if why:
            rows.append((path, "code", why))
            continue
        if status in ("removed", "renamed"):
            rows.append((path, "code", f"{status} (moving or deleting a page is structural)"))
            continue
        kind = S.page_kind(path)
        if kind is None:
            rows.append((path, "code", "matches neither list (fails closed)"))
            continue
        if kind in ("image", "sitemap"):
            rows.append((path, "content", kind))
            continue

        # An HTML page. The path says content; now make sure the edit does.
        head = src.head_text(path)
        base = src.base_text(path) if status != "added" else None
        problems = []

        novel = [b for b in S.active_blocks(head) if b not in corpus]
        for b in novel:
            problems.append("new script/form/schema/tracking block not already on the site: "
                            f"`{b[:90]}`")

        if base is not None:
            _, out_base = S.split_main(base)
            main_head, out_head = S.split_main(head)
            if not main_head:
                problems.append("page has no <main> element")
            elif S.norm(out_base) != S.norm(out_head):
                problems.append("changes outside <main> (head, header or footer)")
        elif not S.split_main(head)[0]:
            problems.append("new page has no <main> element")

        if problems:
            rows.append((path, "code", "; ".join(problems)))
        else:
            what = "new " + kind if status == "added" else kind + ", copy inside <main> only"
            rows.append((path, "content", what))

    verdict = "content" if all(v == "content" for _, v, _ in rows) else "code"
    return verdict, rows


def summary(verdict, rows):
    lines = []
    if verdict == "content":
        lines.append("### content-classification: **content only**")
        lines.append("")
        lines.append("Every changed file is content under GLOBAL §8a. This PR may merge "
                     "automatically once every required check passes.")
    else:
        lines.append("### content-classification: **code — Bill merges**")
        lines.append("")
        lines.append("At least one changed file is code, or could not be proven to be "
                     "content (GLOBAL §8a). Auto-merge stays off.")
    lines.append("")
    lines.append("| File | Verdict | Why |")
    lines.append("|---|---|---|")
    # Code rows first: they are the ones that decided it.
    for path, v, why in sorted(rows, key=lambda r: r[1] != "code"):
        lines.append(f"| `{path}` | {v} | {why.replace('|', '/')} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pr", type=int)
    g.add_argument("--git", nargs=2, metavar=("BASE", "HEAD"))
    a = ap.parse_args()

    if a.git:
        src = GitSource(*a.git)
    else:
        src = ApiSource(os.environ["GITHUB_REPOSITORY"], a.pr, os.environ["HEAD_SHA"])

    try:
        verdict, rows = classify(src)
    except Exception as e:  # anything unexpected is a code verdict, loudly
        verdict, rows = "code", [("(classifier)", "code", f"error: {e}")]

    text = summary(verdict, rows)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"verdict={verdict}\n")
    print(f"verdict={verdict}")


if __name__ == "__main__":
    main()
