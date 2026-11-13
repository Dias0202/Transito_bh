"""Publish site/dist to the public GitHub Pages repo (Dias0202/transito-bh).

Only the built static site goes public: HTML/JS/CSS, aggregated JSON, README and
LICENSE. The token is read from the PAGES_TOKEN environment variable and passed
as a one-off HTTP header: it is never written to disk or to git config.

    cd site && npm run build && cd ..
    set PAGES_TOKEN=...            (PowerShell: $env:PAGES_TOKEN="...")
    python scripts/publish_pages.py "Update data through Jul 2026"
"""
from __future__ import annotations

import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "site" / "dist"
WORK = ROOT / "out" / "pages_repo"
REMOTE = "https://github.com/Dias0202/transito-bh.git"
NAME, EMAIL = "Gabriel Dias Moreira", "98992689+Dias0202@users.noreply.github.com"
KEEP = {".git", "README.md", "LICENSE", ".nojekyll"}
# Extra terms that must never reach the public site (comma-separated, case-insensitive),
# kept out of the repository: PUBLISH_FORBIDDEN_TERMS="term1,term2".
FORBIDDEN = ("claude", "anthropic") + tuple(
    t.strip().lower() for t in os.environ.get("PUBLISH_FORBIDDEN_TERMS", "").split(",") if t.strip()
)


def git(*args: str, cwd: Path = WORK, token: str | None = None) -> str:
    pre = ["git", "-c", "credential.helper="]
    if token:
        auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        pre += ["-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {auth}"]
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(pre + list(args), cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout


def main(message: str) -> None:
    token = os.environ["PAGES_TOKEN"]
    if not (DIST / "index.html").exists():
        sys.exit("site/dist missing: run `npm run build` in site/ first")
    if not (WORK / ".git").exists():
        WORK.parent.mkdir(parents=True, exist_ok=True)
        git("clone", REMOTE, str(WORK), cwd=WORK.parent, token=token)
    git("pull", "--ff-only", token=token)
    for p in WORK.iterdir():
        if p.name not in KEEP:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    shutil.copytree(DIST, WORK, dirs_exist_ok=True)
    (WORK / ".nojekyll").touch()
    for f in WORK.rglob("*"):
        if f.is_file() and ".git" not in f.parts and f.suffix in {".html", ".js", ".css", ".json", ".md"}:
            text = f.read_text("utf-8", errors="ignore").lower()
            bad = [w for w in FORBIDDEN if w in text]
            if bad:
                sys.exit(f"refusing to publish: {f.relative_to(WORK)} mentions {bad}")
    git("config", "user.name", NAME)
    git("config", "user.email", EMAIL)
    git("add", "-A")
    if not git("status", "--porcelain").strip():
        print("nothing to publish")
        return
    git("commit", "-q", "-m", message)
    git("push", "origin", "main", token=token)
    print("published:", git("log", "-1", "--format=%h %s").strip())


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Update site")
