# One-time setup

Everything is free. Keys go only into GitHub's encrypted Secrets, never into a file or a chat.
Claude guides each step one screen at a time.

## A. GitHub
1. Repo `growtharcco-sudo/the-unhyped-studio`, Public (done).
2. github.com/settings/installations → Claude → Configure → add `the-unhyped-studio` (so Claude can push).
3. After Claude's first push: repo → Settings → Pages → Source *Deploy from a branch* → `media` / `(root)` → Save.

## B. Instagram key (never expires): Meta system user
1. @theunhyped.ai must be a Professional account linked to a Facebook Page (Page "The Unhyped").
2. business.facebook.com → your Business portfolio → add the Page and the Instagram account as assets.
3. developers.facebook.com → My Apps → a Business app (the finance app can be reused) with Instagram API
   (Facebook login) permissions: `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
   `pages_read_engagement`, `business_management`.
4. Business settings → Users → System users → Add (Admin) → Assign assets: the app (full control),
   the Page and the Instagram account → Generate new token → expiration **Never** → tick the permissions above.
   That token is `IG_TOKEN` (starts with EAA).
5. `IG_USER_ID`: leave it empty at first and run **Actions → Check keys**: it prints the ID to use.

## C. YouTube key (Google Cloud)
1. console.cloud.google.com → New project `the-unhyped` (its own project, so it has its own daily upload quota).
2. APIs & Services → Library → YouTube Data API v3 → Enable.
3. OAuth consent screen → External → app name `Unhyped Studio`, scope `.../auth/youtube.upload`,
   home page https://growtharcco-sudo.github.io/the-unhyped-studio/ (privacy.html and terms.html are there)
   → **Publish app** (status "In production"; in "Testing" the key dies after 7 days).
4. Credentials → Create credentials → OAuth client ID → Desktop app → Download JSON.
5. On a laptop: `pip3 install google-auth-oauthlib` then
   `python3 tools/get_youtube_token.py ~/Downloads/client_secret_XXXX.json`, sign in with the Google account
   that owns @theunhypedai. It prints `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
6. Apply for the free audit so uploads can be public: https://support.google.com/youtube/contact/yt_api_form
   Until it is approved, YouTube keeps API uploads **private**: switch each Short to Public in YouTube Studio.

## D. Secrets
Repo → Settings → Secrets and variables → Actions → New repository secret, one each:
`IG_TOKEN`, `IG_USER_ID`, `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

## E. Test (posts nothing publicly)
1. Actions → **Check keys** → Run workflow (reads account info only).
2. Actions → **Deep check** → Run workflow: Instagram processes the test Reel without publishing it, and
   YouTube receives a PRIVATE test upload (delete it in YouTube Studio afterwards).

## F. Scheduled tasks (Claude)
Three cloud tasks follow `ROUTINE.md`: Daily (evening + morning), News, Breaking watcher (every 3 h).
Each needs "Skip all approvals" (Automatically approve) and no connectors it doesn't use.
