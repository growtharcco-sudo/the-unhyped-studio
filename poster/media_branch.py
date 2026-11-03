"""The `media` branch holds only the videos waiting to be posted, served by GitHub Pages.

It is rebuilt as a single fresh commit every time, so its history never grows.
  python poster/media_branch.py add <id> <video.mp4> <cover.png>   # queue a video
  python poster/media_branch.py prune                               # drop everything already posted
"""
import os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(*a, cwd=None, check=True):
    return subprocess.run(a, cwd=cwd, check=check, text=True, capture_output=True)


def _url():
    """In GitHub Actions use the job's token; locally (or in Claude's workspace) git's own credentials apply."""
    url = sh("git", "remote", "get-url", "origin", cwd=ROOT).stdout.strip()
    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if tok and repo: url = f"https://x-access-token:{tok}@github.com/{repo}.git"
    return url


def _checkout():
    url = _url()
    tmp = tempfile.mkdtemp()
    r = sh("git", "clone", "--depth", "1", "--branch", "media", url, tmp, check=False)
    if r.returncode:                               # first run: no media branch yet
        shutil.rmtree(tmp); os.makedirs(tmp)
        sh("git", "init", "-q", cwd=tmp); sh("git", "remote", "add", "origin", url, cwd=tmp)
    return tmp


def _publish(tmp):
    open(os.path.join(tmp, ".nojekyll"), "w").close()
    site = os.path.join(ROOT, "pages")                      # home, privacy and terms pages always stay on the site
    for f in os.listdir(site) if os.path.isdir(site) else []:
        shutil.copy(os.path.join(site, f), os.path.join(tmp, f))
    shutil.rmtree(os.path.join(tmp, ".git"), ignore_errors=True)
    url = _url()
    sh("git", "init", "-q", "-b", "media", cwd=tmp)
    sh("git", "config", "user.name", "unhyped-bot", cwd=tmp); sh("git", "config", "user.email", "unhyped-bot@users.noreply.github.com", cwd=tmp)
    sh("git", "add", "-A", cwd=tmp); sh("git", "commit", "-q", "-m", "media queue", "--allow-empty", cwd=tmp)
    sh("git", "push", "-q", "-f", url, "media", cwd=tmp)


def add(vid, video, cover):
    """Add a video, then re-check it is really on the branch (another run may have pushed at the same moment)."""
    import time
    for attempt in range(4):
        tmp = _checkout()
        d = os.path.join(tmp, vid); os.makedirs(d, exist_ok=True)
        shutil.copy(video, os.path.join(d, "video.mp4")); shutil.copy(cover, os.path.join(d, "cover.png"))
        _publish(tmp)
        time.sleep(5)
        chk = _checkout()
        if os.path.exists(os.path.join(chk, vid, "video.mp4")): print("media branch has", vid); return
        print("video was overwritten by a parallel run, retrying"); time.sleep(10)
    raise SystemExit("could not add video to media branch")


def prune():
    tmp = _checkout()
    queued = set(os.listdir(os.path.join(ROOT, "queue"))) if os.path.isdir(os.path.join(ROOT, "queue")) else set()
    for name in os.listdir(tmp):
        if name.startswith((".", "_")) or name in queued or name.endswith(".html"): continue   # _test stays for the deep check
        shutil.rmtree(os.path.join(tmp, name), ignore_errors=True)
    _publish(tmp)


if __name__ == "__main__":
    if sys.argv[1] == "add": add(*sys.argv[2:5])
    elif sys.argv[1] == "check": print("on media branch" if os.path.exists(os.path.join(_checkout(), sys.argv[2], "video.mp4")) else "MISSING")
    elif sys.argv[1] == "prune": prune()
