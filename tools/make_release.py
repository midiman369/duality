#!/usr/bin/env python3
"""Build a release branch for main from dev: only the files a user needs.

    python3 tools/make_release.py 1.0.0          creates release/1.0.0 from origin/main (in a temporary worktree)
    python3 tools/make_release.py 1.0.0 --push   ... and pushes it to origin (then open the pull request into main)

The release tree is RELEASE (files and folders) taken from the current dev commit; everything else on main is
removed, so tests, tools, CLAUDE.md, .claude/ and the regression data never reach main. dev is never merged into
main and main is never merged back into dev: each release is one commit on main, "Release <version>".
Checks before committing: a clean dev checkout, VERSION in duality.py equals the version given, a CHANGELOG entry
for it, and the release tree compiles and runs `duality.py --version` on its own.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE = ["duality.py", "tables_8850.py", "tables_anima.py", "tables_cm64.py", "tables_gs.py", "tables_voices.py",
           "tables_voodoo.py", "tables_xg.py", "voodoo_banks.py", "requirements.txt", "LICENSE", "README.md",
           "CHANGELOG.md", ".gitignore", "docs/images"]


def git(*args, cwd=REPO, capture=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=capture, text=True)
    if r.returncode:
        sys.exit(f"git {' '.join(args)} failed:\n{r.stderr}")
    return r.stdout.strip() if capture else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("version")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--trailer", action="append", default=[], help="a commit trailer (repeatable)")
    a = ap.parse_args()
    v = a.version
    if git("status", "--porcelain"):
        sys.exit("the checkout has uncommitted changes: commit them on dev first")
    src = git("rev-parse", "HEAD")
    head = open(os.path.join(REPO, "duality.py")).read().split("\n", 3)[:3]
    if f'VERSION = "{v}"' not in head:
        sys.exit(f"duality.py says {head[1]!r}, not {v}")
    if f"## {v} " not in open(os.path.join(REPO, "CHANGELOG.md")).read():
        sys.exit(f"CHANGELOG.md has no '## {v}' entry")
    git("fetch", "-q", "origin", "main")
    branch = f"release/{v}"
    tmp = tempfile.mkdtemp(prefix="duality-release-")
    wt = os.path.join(tmp, "tree")
    git("worktree", "add", "-q", "-B", branch, wt, "origin/main")
    try:
        git("rm", "-q", "-r", "--ignore-unmatch", ".", cwd=wt)
        git("checkout", src, "--", *RELEASE, cwd=wt)
        files = git("ls-files", cwd=wt).split("\n")
        extra = [f for f in files if not any(f == r or f.startswith(r + "/") for r in RELEASE)]
        if extra:
            sys.exit(f"not in the release list: {extra}")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for f in files:
            if f.endswith(".py"):
                subprocess.run([sys.executable, "-m", "py_compile", f], cwd=wt, check=True, env=env)
        out = subprocess.run([sys.executable, "-E", "-s", "duality.py", "--version"], cwd=wt, capture_output=True,
                             text=True, env=env)
        if out.returncode or out.stdout.strip() != f"Duality {v}":
            sys.exit(f"the release tree does not run on its own:\n{out.stdout}{out.stderr}")
        shutil.rmtree(os.path.join(wt, "__pycache__"), ignore_errors=True)
        if not git("status", "--porcelain", cwd=wt):
            sys.exit("main already holds exactly this release")
        git("commit", "-q", "-m", f"Release {v}\n\nBuilt by tools/make_release.py from dev {src[:7]}.",
            *[x for t in a.trailer for x in ("--trailer", t)], cwd=wt)
        print(git("show", "--stat", "--format=%h %s", "HEAD", cwd=wt))
        if a.push:
            git("push", "-q", "-u", "origin", branch, cwd=wt, capture=False)
            print(f"pushed {branch}: open a pull request {branch} -> main, merge it, then tag v{v} on main")
        else:
            print(f"branch {branch} is ready; push it with: git push -u origin {branch}")
    finally:
        git("worktree", "remove", "--force", wt)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
