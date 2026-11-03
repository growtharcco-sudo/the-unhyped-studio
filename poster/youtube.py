"""Upload a Short with the official YouTube Data API v3.

Needs: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN (scope youtube.upload).
Note: until Google audits the API project, YouTube forces API uploads to private.
"""
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def _client():
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token",
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_short(path, title, description, tags=None, privacy=None):
    privacy = privacy or os.environ.get("YT_PRIVACY", "public")
    body = {"snippet": {"title": title[:100], "description": description[:4900], "tags": tags or [],
                        "categoryId": "28", "defaultLanguage": "en", "defaultAudioLanguage": "en"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False,
                       "containsSyntheticMedia": True}}          # the "altered or synthetic content" disclosure
    yt = _client()
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(path, mimetype="video/mp4", resumable=True, chunksize=8 << 20))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return {"yt_video_id": resp["id"], "yt_url": f"https://youtube.com/shorts/{resp['id']}",
            "yt_privacy": resp.get("status", {}).get("privacyStatus")}
