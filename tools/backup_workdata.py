#!/usr/bin/env python3
"""Back up Duality's git-ignored work to the user's private Gitea repo duality-workdata (never to GitHub).

    python3 tools/backup_workdata.py            back up this session now (foreground, prints what it does)
    python3 tools/backup_workdata.py --dry-run  list what would be copied, change nothing
    python3 tools/backup_workdata.py --hook     the Stop / SessionEnd hook: at most every BACKUP_INTERVAL seconds
                                                (default 1800), in a detached background process; --force skips the wait
    python3 tools/backup_workdata.py --clone    only make sure the clone exists (beside this checkout) and is current,
                                                for working on its songs/ (the song generators live only there)

What it copies (add and update only: nothing is ever deleted from the backup):
    scratchpad/<session>/        the session's scratchpad (no __pycache__, no backup tarballs)
    uploads/<session>/           the files the user uploaded into the session
    session-images/<session>/    images pasted into the chat
    transcripts/<session>/       transcript/part-NNNN.jsonl.gz (the session's .jsonl in 32 MiB pieces of complete
                                 lines, each gzipped on its own: concatenated they gunzip to the transcript, and a
                                 piece once written never changes, so a run uploads only new pieces) and files/
                                 (the transcript's side files)
    memory/<session>/            conversation.md, user-requests.md, compaction-summaries.md (tools/transcript_memory.py),
                                 plans/, tasks/, dev-commits.txt, SESSION.md
    tests-midi/, recordings/, logs/, checkout-ignored/.claude/   from the Duality checkout
    manifests/<session>.sha256   the checksum of every file this session's runs wrote
Images, PDFs, zips and the transcript pieces go to Git LFS. A run stages only those folders (OWNED), so work in
progress elsewhere in the clone (songs/, edited and committed by hand) is never swept into a backup commit.

Configuration (environment variables): GITEA_TOKEN (an access token with repository read/write) and
GITEA_BACKUP_URL (the repo's https URL); the URL may instead sit in ~/.config/duality-backup.env as
GITEA_BACKUP_URL=... . The token reaches git only through a one-off credential helper that reads the variable: it is
never written to a file, a URL, git config or a commit, and a file that contains it is not copied. The local clone is
the checkout's sibling duality-workdata/ (BACKUP_CLONE overrides), cloned without LFS content. Runs only in Claude
Code cloud sessions (CLAUDE_CODE_REMOTE=true) unless --any-host. State and log: ~/.cache/duality-backup/.
"""
import argparse
import fcntl
import glob
import gzip
import hashlib
import json
import mmap
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
STATE = Path.home() / ".cache" / "duality-backup"
LOG = STATE / "backup.log"
CHUNK = 32 << 20                    # transcript piece size (raw bytes, cut at line ends)
MAX_FILE = 200 << 20                # larger files are left out (logged)
SCAN_LIMIT = 64 << 20               # files up to this size are scanned for credentials before copying
LFS_PATTERNS = ["*.png", "*.PNG", "*.pdf", "*.PDF", "*.zip", "*.ZIP", "*.jpg", "*.jpeg", "*.JPG", "*.gif", "*.wav",
                "*.mp3", "*.flac", "*.ogg", "*.mp4", "*.tar", "*.7z", "*.gz.part-*", "*.jsonl.gz"]
SKIP_DIRS = {"__pycache__", ".git"}
OWNED = ["scratchpad", "uploads", "session-images", "transcripts", "memory", "manifests", "tests-midi", "recordings",
         "logs", "checkout-ignored", ".gitattributes"]
SKIP_FILE = re.compile(r"(\.pyc$|^duality-workdata-.*\.tar(\.gz)?$)")
CRED = re.compile(rb"ghp_[A-Za-z0-9]{30,}|gho_[A-Za-z0-9]{30,}|ghs_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|"
                  rb"sk-ant-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
HELPER = ('!f() { test "$1" = get && printf "username=%s\\npassword=%s\\n" "${GITEA_USER:-backup}" '
          '"$GITEA_TOKEN"; }; f')


def log(msg, echo=False):
    STATE.mkdir(parents=True, exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    with open(LOG, "a") as f:
        f.write(line + "\n")
    if echo:
        print(msg)


def config():
    url = os.environ.get("GITEA_BACKUP_URL", "").strip()
    env = Path.home() / ".config" / "duality-backup.env"
    if not url and env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("GITEA_BACKUP_URL="):
                url = line.split("=", 1)[1].strip()
    token = os.environ.get("GITEA_TOKEN", "")
    if "github.com" in url:
        raise SystemExit("refusing: the backup never goes to GitHub")
    return url, token


def git(clone, *args, check=True, env=None, capture=True):
    e = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1", **(env or {}))
    r = subprocess.run(["git", "-c", "credential.helper=", "-c", f"credential.helper={HELPER}", *args],
                       cwd=clone, env=e, capture_output=capture, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args[:2])} failed: {(r.stderr or '').strip()[-400:]}")
    return r


def ensure_lfs():
    if subprocess.run(["git", "lfs", "version"], capture_output=True).returncode == 0:
        return
    log("installing git-lfs")
    q = dict(capture_output=True)
    if subprocess.run(["apt-get", "install", "-y", "git-lfs"], **q).returncode:
        subprocess.run(["apt-get", "update"], **q)
        subprocess.run(["apt-get", "install", "-y", "git-lfs"], **q, check=True)


def ensure_clone(url):
    clone = Path(os.environ.get("BACKUP_CLONE", REPO.parent / "duality-workdata"))
    owner = url.rstrip("/").split("/")[-2] if url.count("/") >= 4 else "backup"
    os.environ.setdefault("GITEA_USER", owner)
    if not (clone / ".git").exists():
        log(f"cloning the backup repo into {clone} (no LFS content)")
        git(REPO.parent, "clone", url, str(clone))
    origin = git(clone, "config", "--get", "remote.origin.url").stdout.strip()
    if origin != url or "github.com" in origin:
        raise RuntimeError(f"{clone} points at another remote; leaving it alone")
    git(clone, "lfs", "install", "--local")
    git(clone, "config", "lfs.locksverify", "false")
    git(clone, "config", "user.name", "Claude")
    git(clone, "config", "user.email", "noreply@anthropic.com")
    attrs = clone / ".gitattributes"
    have = attrs.read_text().split("\n") if attrs.exists() else []
    missing = [p for p in LFS_PATTERNS if not any(l.startswith(p + " ") for l in have)]
    if missing:
        with open(attrs, "a") as f:
            for p in missing:
                f.write(f"{p} filter=lfs diff=lfs merge=lfs -text\n")
    return clone


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def lfs_oid(p):
    """The sha256 an LFS pointer file names, else None."""
    try:
        if p.stat().st_size > 400:
            return None
        text = p.read_text()
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("version https://git-lfs"):
        return None
    m = re.search(r"oid sha256:([0-9a-f]{64})", text)
    return m.group(1) if m else None


def has_secret(p, token, size):
    if size > SCAN_LIMIT:
        with open(p, "rb") as f:
            prev = b""
            for block in iter(lambda: f.read(8 << 20), b""):
                buf = prev + block
                if (token and token.encode() in buf) or CRED.search(buf):
                    return True
                prev = block[-4096:]
        return False
    data = p.read_bytes()
    return bool((token and token.encode() in data) or CRED.search(data))


class Run:
    def __init__(self, clone, sid, token, dry):
        self.clone, self.sid, self.token, self.dry = clone, sid, token, dry
        self.cache_path = STATE / "files.json"
        try:
            self.cache = json.loads(self.cache_path.read_text())
        except (OSError, ValueError):
            self.cache = {}
        self.man_path = clone / "manifests" / f"{sid}.sha256"
        self.manifest = {}
        if self.man_path.exists():
            for line in self.man_path.read_text().splitlines():
                h, _, rel = line.partition("  ")
                if rel:
                    self.manifest[rel] = h
        self.copied, self.bytes, self.skipped = [], 0, []

    def put(self, src, rel):
        """Copy src to rel in the clone when it is new or changed there."""
        try:
            st = src.stat()
        except OSError:
            return
        if st.st_size > MAX_FILE:
            self.skipped.append(f"{rel} ({st.st_size >> 20} MiB, over the limit)")
            return
        key = [st.st_size, st.st_mtime_ns]
        hit = self.cache.get(rel)
        dest = self.clone / rel
        if hit and hit[:2] == key and (dest.exists() or dest.is_symlink()):
            return
        h = sha256_file(src)
        if dest.exists():
            oid = lfs_oid(dest)
            same = (oid == h) if oid else (dest.stat().st_size == st.st_size and sha256_file(dest) == h)
            if same:
                self.cache[rel] = key + [h]
                self.manifest.setdefault(rel, h)
                return
        if has_secret(src, self.token, st.st_size):
            self.skipped.append(f"{rel} (holds a credential)")
            return
        self.copied.append(rel)
        self.bytes += st.st_size
        if not self.dry:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            self.cache[rel] = key + [h]
            self.manifest[rel] = h

    def tree(self, src_dir, rel_dir, only=None):
        src_dir = Path(src_dir)
        if not src_dir.is_dir():
            return
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(files):
                if SKIP_FILE.search(name) or (only and name not in only):
                    continue
                p = Path(root) / name
                if p.is_symlink() or not p.is_file():
                    continue
                self.put(p, f"{rel_dir}/{p.relative_to(src_dir).as_posix()}")

    def transcript(self, src):
        """The transcript in pieces of complete lines (CHUNK bytes or so), each gzipped deterministically."""
        rel_dir = f"transcripts/{self.sid}/transcript"
        out = self.clone / rel_dir
        idx_path = out / "index.json"
        try:
            old = {e["part"]: e for e in json.loads(idx_path.read_text())["parts"]}
        except (OSError, ValueError, KeyError):
            old = {}
        with open(src, "rb") as f:
            n = os.fstat(f.fileno()).st_size
            if n == 0:
                return
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            try:
                if self.token and mm.find(self.token.encode()) >= 0:
                    self.skipped.append(f"{rel_dir} (the transcript holds the token)")
                    return
                parts, start, k = [], 0, 0
                while start < n:
                    target = start + CHUNK
                    if target < n:
                        nl = mm.find(b"\n", target - 1)
                        end = nl + 1 if nl >= 0 else n
                    else:
                        end = n
                    if end == n:
                        last = mm.rfind(b"\n", start, n)
                        if last < 0:
                            break
                        end = last + 1
                    raw = mm[start:end]
                    h = hashlib.sha256(raw).hexdigest()
                    name = f"part-{k:04d}.jsonl.gz"
                    prev = old.get(k)
                    if not (prev and prev["start"] == start and prev["end"] == end and prev["raw_sha256"] == h
                            and (out / name).exists()):
                        gz = gzip.compress(raw, compresslevel=6, mtime=0)
                        prev = {"part": k, "start": start, "end": end, "raw_sha256": h,
                                "gz_sha256": hashlib.sha256(gz).hexdigest()}
                        self.copied.append(f"{rel_dir}/{name}")
                        self.bytes += len(gz)
                        if not self.dry:
                            out.mkdir(parents=True, exist_ok=True)
                            (out / name).write_bytes(gz)
                    self.manifest[f"{rel_dir}/{name}"] = prev["gz_sha256"]
                    parts.append(prev)
                    start, k = end, k + 1
            finally:
                mm.close()
        if not self.dry and parts:
            out.mkdir(parents=True, exist_ok=True)
            idx = {"session": self.sid, "bytes": parts[-1]["end"], "chunk": CHUNK, "parts": parts,
                   "rejoin": "cat part-*.jsonl.gz | gunzip > session.jsonl"}
            text = json.dumps(idx, indent=1) + "\n"
            if not idx_path.exists() or idx_path.read_text() != text:
                idx_path.write_text(text)

    def generated(self, path, rel):
        """A generated file: copy it when its content differs from the clone's."""
        self.cache.pop(rel, None)
        self.put(Path(path), rel)

    def finish(self):
        if self.dry:
            return
        self.man_path.parent.mkdir(parents=True, exist_ok=True)
        self.man_path.write_text("".join(f"{h}  {rel}\n" for rel, h in sorted(self.manifest.items())))
        STATE.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cache))
        tmp.replace(self.cache_path)


def session_paths(sid, transcript):
    home = Path.home()
    sp = sorted(glob.glob(f"/tmp/claude-*/*/{sid}/scratchpad"))
    base = Path(sp[0]).parent if sp else None
    if not transcript:
        found = sorted(glob.glob(str(home / ".claude" / "projects" / "*" / f"{sid}.jsonl")))
        transcript = found[0] if found else None
    side = Path(transcript).with_suffix("") if transcript else None
    return {"scratchpad": base / "scratchpad" if base else None, "images": base / "images" if base else None,
            "uploads": home / ".claude" / "uploads" / sid, "transcript": Path(transcript) if transcript else None,
            "side": side, "plans": home / ".claude" / "plans", "tasks": home / ".claude" / "tasks" / sid}


def backup(sid, transcript, dry=False, echo=True):
    url, token = config()
    if not url or not token:
        log("not configured (GITEA_BACKUP_URL / GITEA_TOKEN): nothing done", echo)
        return 0
    ensure_lfs()
    clone = ensure_clone(url)
    git(clone, "pull", "--rebase", "--autostash", "-q", "origin", "main", check=False)
    paths = session_paths(sid, transcript)
    r = Run(clone, sid, token, dry)
    r.tree(paths["scratchpad"], f"scratchpad/{sid}")
    r.tree(paths["uploads"], f"uploads/{sid}")
    r.tree(paths["images"], f"session-images/{sid}")
    r.tree(paths["side"], f"transcripts/{sid}/files")
    r.tree(paths["plans"], f"memory/{sid}/plans")
    r.tree(paths["tasks"], f"memory/{sid}/tasks")
    r.tree(REPO / "tests" / "midi", "tests-midi")
    r.tree(REPO / "recordings", "recordings")
    r.tree(REPO / "logs", "logs")
    r.tree(REPO / ".claude", "checkout-ignored/.claude", only={"settings.local.json"})
    if paths["transcript"] and paths["transcript"].exists():
        r.transcript(paths["transcript"])
        with tempfile.TemporaryDirectory() as tmp:
            sys.path.insert(0, str(HERE))
            import transcript_memory
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                transcript_memory.main(str(paths["transcript"]), tmp)
            commits = subprocess.run(["git", "log", "--date=iso-strict", "--format=%ad %h %s", "dev"], cwd=REPO,
                                     capture_output=True, text=True).stdout
            Path(tmp, "dev-commits.txt").write_text(commits)
            rid = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "")
            link = "https://claude.ai/code/session_" + rid[4:] if rid.startswith("cse_") else "(not a cloud session)"
            Path(tmp, "SESSION.md").write_text(
                f"# Session {sid}\n\n- claude.ai: {link}\n- Duality checkout: {REPO} (dev at "
                f"{subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip()})\n"
                f"- backed up by tools/backup_workdata.py\n")
            for name in ("conversation.md", "user-requests.md", "compaction-summaries.md", "dev-commits.txt",
                         "SESSION.md"):
                r.generated(Path(tmp, name), f"memory/{sid}/{name}")
    r.finish()
    for s in r.skipped:
        log(f"left out: {s}", echo)
    if dry:
        log(f"dry run: {len(r.copied)} files, {r.bytes / 2**20:.1f} MiB would be copied", echo)
        for rel in r.copied[:40]:
            print("  " + rel)
        return 0
    git(clone, "add", "-A", "--", *[o for o in OWNED if (clone / o).exists()])
    if git(clone, "diff", "--cached", "--quiet", check=False).returncode == 0:
        log("no changes", echo)
        return 0
    msg = (f"backup: session {sid[:8]}, {len(r.copied)} files, {r.bytes / 2**20:.1f} MiB\n\n"
           f"Session {sid}; written by tools/backup_workdata.py at {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}.")
    git(clone, "commit", "-q", "-m", msg)
    for attempt in range(3):
        p = git(clone, "push", "-q", "origin", "HEAD:main", check=False)
        if p.returncode == 0:
            head = git(clone, "rev-parse", "--short", "HEAD").stdout.strip()
            log(f"pushed {head}: {len(r.copied)} files, {r.bytes / 2**20:.1f} MiB", echo)
            (STATE / "last-push").write_text(head + "\n")
            return 0
        log(f"push failed ({(p.stderr or '').strip()[-200:]}); rebasing and retrying", echo)
        if git(clone, "pull", "--rebase", "--autostash", "-q", "origin", "main", check=False).returncode:
            git(clone, "rebase", "--abort", check=False)
            break
        time.sleep(5 * (attempt + 1))
    log("push did not go through; the commit waits in the clone for the next run", echo)
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hook", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--clone", action="store_true")
    ap.add_argument("--run", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--any-host", action="store_true")
    ap.add_argument("--session")
    ap.add_argument("--transcript")
    a = ap.parse_args()
    if os.environ.get("CLAUDE_CODE_REMOTE") != "true" and not a.any_host:
        return 0
    if a.clone:
        url, token = config()
        if not url or not token:
            print("not configured: GITEA_BACKUP_URL / GITEA_TOKEN are not set")
            return 1
        ensure_lfs()
        clone = ensure_clone(url)
        r = git(clone, "pull", "--rebase", "--autostash", "-q", "origin", "main", check=False)
        print(f"{clone}" + ("" if r.returncode == 0 else " (pull failed: working on the local copy)"))
        return 0
    payload = {}
    if a.hook and not sys.stdin.isatty():
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            payload = {}
    sid = a.session or payload.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID")
    transcript = a.transcript or payload.get("transcript_path")
    if not sid:
        return 0
    STATE.mkdir(parents=True, exist_ok=True)
    if a.hook:
        stamp = STATE / "last-run"
        interval = float(os.environ.get("BACKUP_INTERVAL", "1800"))
        if not a.force and stamp.exists() and time.time() - stamp.stat().st_mtime < interval:
            return 0
        url, token = config()
        if not url or not token:
            return 0
        stamp.touch()
        cmd = [sys.executable, str(Path(__file__).resolve()), "--run", "--session", sid]
        if transcript:
            cmd += ["--transcript", transcript]
        with open(LOG, "a") as out:
            subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True)
        return 0
    lock = open(STATE / "lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | (fcntl.LOCK_NB if a.run else 0))
    except BlockingIOError:
        log("another backup is running: skipped")
        return 0
    try:
        return backup(sid, transcript, dry=a.dry_run, echo=not a.run)
    except Exception as e:  # noqa: BLE001 - a backup failure must never break the session
        log(f"backup failed: {e}", not a.run)
        return 1


if __name__ == "__main__":
    sys.exit(main())
