"""One-time: get the YouTube refresh token. Run on your Mac, sign in with the Google account that owns the channel.

  pip3 install google-auth-oauthlib
  python3 tools/get_youtube_token.py path/to/client_secret.json

It prints YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN to paste into GitHub Secrets.
"""
import json, sys
from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], ["https://www.googleapis.com/auth/youtube.upload"])
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
cfg = json.load(open(sys.argv[1]))
cfg = cfg.get("installed") or cfg.get("web")
print("\nPaste these into GitHub > Settings > Secrets and variables > Actions:\n")
print("YT_CLIENT_ID     =", cfg["client_id"])
print("YT_CLIENT_SECRET =", cfg["client_secret"])
print("YT_REFRESH_TOKEN =", creds.refresh_token)
