# The Unhyped Studio

Fully automatic, free pipeline for The Unhyped (Instagram @theunhyped.ai, YouTube @theunhypedai).

| Time (IST) | What happens | Where |
|---|---|---|
| ~3:40 PM | Research, write, fact-check, voice (Kokoro "Liam") and build the evening (22:00) and next morning (08:00) Reels, queue them, send them to the owner | Claude scheduled task (cloud), `ROUTINE.md` section A |
| ~4:40 PM | Same for the news Reel (18:30) | Claude scheduled task, section B |
| every 3 h | Breaking watcher: posts within minutes if something huge happens (max 2 a day, replaces the news Reel) | Claude scheduled task, section C |
| until post time | The owner can reply "skip" or ask for changes | Claude |
| 08:00 / 18:30 / 22:00 | Post to Instagram Reels (official API, AI label on) and YouTube Shorts (official API, synthetic-content disclosure on) | GitHub Actions `post.yml` (waits for the exact minute itself) and `post-now.yml` (breaking) |

Nothing needs a laptop. Setup: see `SETUP.md`.

## Folders
- `pipeline/` voice + word alignment (`voice.py`), engineering-sheet video engine (`render.py`), builder and rules checker (`make_reel.py`)
- `specs/` one JSON file per Reel: phrases, scenes, cover, captions, sources, math
- `queue/` Reels waiting to post (`post.json`); videos live on the `media` branch (GitHub Pages)
- `posted/` what went out, with Instagram and YouTube links in `result.json`
- `poster/` Instagram and YouTube posting, media branch handling
- `IDEAS.md` idea bank; `NEWS_LOG.md` news and breaking log; `ROUTINE.md` the instructions Claude follows

## Manual commands
```
python pipeline/make_reel.py specs/<id>.json --check    # rules only
python pipeline/make_reel.py specs/<id>.json --stills   # preview frames + cover
python pipeline/make_reel.py specs/<id>.json            # build video + cover into queue/<id>/
python poster/media_branch.py add <id> queue/<id>/video.mp4 queue/<id>/cover.png
python poster/publish_due.py --dry-run                  # show what would post now
```
Voice: Kokoro v1.0 (Apache 2.0), downloaded on first use. Word timing: pocketsphinx (BSD). Fonts: IBM Plex (SIL OFL).
