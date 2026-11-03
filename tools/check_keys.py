"""Check that the Instagram and YouTube keys work. Reads account info only; posts nothing."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "poster"))
import requests
ok = True
tok, uid = os.environ.get("IG_TOKEN", ""), os.environ.get("IG_USER_ID", "")
if tok.startswith("EAA") and not uid:
    # system-user token is set but the account ID isn't yet: list the Instagram accounts it can reach
    r = requests.get("https://graph.facebook.com/v26.0/me/accounts",
                     params={"fields": "name,instagram_business_account{id,username}", "access_token": tok}, timeout=30)
    print("Instagram accounts this token can post to (put the id in IG_USER_ID):")
    for pg in (r.json().get("data", []) if r.ok else []):
        ig = pg.get("instagram_business_account")
        print(" ", pg.get("name"), "->", f"@{ig['username']}  IG_USER_ID = {ig['id']}" if ig else "no Instagram account linked")
    if not r.ok: print(" ", r.status_code, r.text[:300])
    ok = False
elif not tok or not uid:
    print("Instagram: IG_TOKEN or IG_USER_ID is missing"); ok = False
else:
    if not uid.isdigit(): print("Instagram: IG_USER_ID should be only digits (17841412838217113)"); ok = False
    import instagram
    base = instagram._base(tok)
    r = requests.get(f"{base}/{uid}", params={"fields": "username", "access_token": tok}, timeout=30)
    print("Instagram:", "OK, connected to @" + r.json().get("username", "?") if r.ok else f"FAILED {r.status_code} {r.text[:300]}")
    ok &= r.ok
    if r.ok:
        r = requests.get(f"{base}/{uid}/content_publishing_limit", params={"fields": "quota_usage,config", "access_token": tok}, timeout=30)
        print("Instagram publishing quota:", r.json() if r.ok else f"could not read ({r.status_code})")
def shape(name, raw):
    """Describe a secret's shape without revealing it."""
    v = raw or ""
    notes = []
    if v != v.strip(): notes.append("has spaces or a line break at the start/end")
    if "=" in v[:20]: notes.append("looks like the label was pasted too (starts with 'NAME =')")
    if name == "YT_CLIENT_ID" and not v.strip().endswith(".apps.googleusercontent.com"): notes.append("should end with .apps.googleusercontent.com")
    if name == "YT_CLIENT_SECRET" and not v.strip().startswith("GOCSPX-"): notes.append("usually starts with GOCSPX-")
    if name == "YT_REFRESH_TOKEN" and not v.strip().startswith("1//"): notes.append("usually starts with 1//")
    print(f"  {name}: {len(v)} characters" + (" -> " + "; ".join(notes) if notes else " -> looks right"))
if os.environ.get("YT_REFRESH_TOKEN"):
    print("YouTube secrets (shape only, never the value):")
    for n in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"): shape(n, os.environ.get(n))
    try:
        import youtube
        from googleapiclient.errors import HttpError
        yt = youtube._client()
        yt._http.credentials.refresh(__import__("google.auth.transport.requests", fromlist=["Request"]).Request())
        print("YouTube: OK, token accepted (upload scope only, so channel name isn't readable)")
    except Exception as e:
        print("YouTube: FAILED", e); ok = False
else:
    print("YouTube: not set up yet")
sys.exit(0 if ok else 1)
