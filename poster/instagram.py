"""Publish a Reel with the Instagram API with Instagram Login (graph.instagram.com).

Needs: IG_USER_ID, IG_TOKEN (long-lived Instagram user token with instagram_business_basic +
instagram_business_content_publish). The video must be reachable at a public URL (GitHub Pages).
"""
import os, time, requests

VER = os.environ.get("IG_API_VERSION", "v26.0")


def _base(token):
    """Instagram-login tokens start with IG...; Facebook/Unified-login (system user) tokens start with EAA."""
    host = "graph.facebook.com" if token.startswith("EAA") else "graph.instagram.com"
    return f"https://{host}/{VER}"


def _check(r):
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram API error {r.status_code}: {r.text[:500]}")
    return r.json()


def publish_reel(video_url, caption, cover_url=None, ai_label=True, token=None, user_id=None):
    token = token or os.environ["IG_TOKEN"]; user_id = user_id or os.environ["IG_USER_ID"]
    BASE = _base(token)
    data = {"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true",
            "access_token": token}
    if cover_url: data["cover_url"] = cover_url
    if ai_label: data["is_ai_generated"] = "true"
    try:
        cid = _check(requests.post(f"{BASE}/{user_id}/media", data=data, timeout=60))["id"]
    except RuntimeError as e:
        if ai_label and "is_ai_generated" in str(e):      # older API versions: retry without the label field
            data.pop("is_ai_generated"); cid = _check(requests.post(f"{BASE}/{user_id}/media", data=data, timeout=60))["id"]
        else:
            raise
    # Instagram downloads and processes the video; poll for up to ~10 minutes
    for _ in range(40):
        st = _check(requests.get(f"{BASE}/{cid}", params={"fields": "status_code,status", "access_token": token},
                                 timeout=30))
        if st.get("status_code") == "FINISHED": break
        if st.get("status_code") in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram could not process the video: {st}")
        time.sleep(15)
    else:
        raise RuntimeError("Instagram processing timed out")
    mid = _check(requests.post(f"{BASE}/{user_id}/media_publish",
                               data={"creation_id": cid, "access_token": token}, timeout=60))["id"]
    link = _check(requests.get(f"{BASE}/{mid}", params={"fields": "permalink", "access_token": token},
                               timeout=30)).get("permalink")
    return {"ig_media_id": mid, "ig_permalink": link}


def refresh_token(token):
    """Instagram-login tokens last 60 days; refreshing returns a fresh 60-day token.
    Facebook/system-user tokens (EAA...) are refreshed differently or never expire, so they are returned unchanged."""
    if token.startswith("EAA"): return token
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=30)
    return _check(r)["access_token"]
