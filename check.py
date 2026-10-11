"""FallenSkullCorp - CurseForge -> Discord guncelleme duyurusu.

Her addonun son dosyasini cfwidget uzerinden kontrol eder; yeni bir dosya
yuklendiyse Discord webhook'una duyuru gonderir.

Ortam degiskenleri:
  DISCORD_WEBHOOK_URL  (zorunlu)  Discord webhook adresi
  CF_API_KEY           (istege bagli) CurseForge API anahtari; varsa
                       duyuruya changelog metni de eklenir.
  DISCORD_ROLE_ID      (istege bagli) Duyuruda etiketlenecek rol
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html import unescape

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(ROOT, "state.json")
ADDONS_PATH = os.path.join(ROOT, "addons.json")
UA = {"User-Agent": "FallenSkullCorp-CF-Webhook/1.0"}


def http_json(url, headers=None, data=None, method=None):
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        return json.loads(body) if body else None


def get_project_api(slug, key):
    """Resmi CurseForge API (gameId 1 = World of Warcraft)."""
    data = http_json(
        f"https://api.curseforge.com/v1/mods/search?gameId=1&slug={slug}",
        headers={"x-api-key": key, "Accept": "application/json"})
    mods = [m for m in (data or {}).get("data", []) if m.get("slug") == slug]
    if not mods:
        return None
    m = mods[0]
    files = []
    for f in m.get("latestFiles") or []:
        files.append({
            "id": f["id"],
            "display": f.get("displayName") or f.get("fileName"),
            "name": f.get("fileName"),
            "url": f"{(m.get('links') or {}).get('websiteUrl', '')}/files/{f['id']}",
            "type": {1: "release", 2: "beta", 3: "alpha"}.get(f.get("releaseType"), "release"),
            "versions": f.get("gameVersions") or [],
            "uploaded_at": f.get("fileDate"),
        })
    return {
        "id": m["id"],
        "title": m.get("name"),
        "urls": {"curseforge": (m.get("links") or {}).get("websiteUrl")},
        "thumbnail": (m.get("logo") or {}).get("thumbnailUrl"),
        "files": files,
    }


def get_project(slug):
    key = os.environ.get("CF_API_KEY")
    if key:
        try:
            p = get_project_api(slug, key)
            if p and p["files"]:
                return p
        except Exception as e:
            print(f"  CurseForge API hatasi ({e}); cfwidget deneniyor")
    # cfwidget ilk istekte projeyi siraya alip 202 donebilir; birkac kez dene
    for _ in range(3):
        try:
            data = http_json(f"https://api.cfwidget.com/wow/addons/{slug}")
            if data and data.get("files"):
                return data
        except urllib.error.HTTPError as e:
            if e.code not in (202, 404, 429, 500, 502, 503):
                raise
        time.sleep(5)
    return None


def latest_file(project):
    files = sorted(project["files"], key=lambda f: f.get("uploaded_at", ""), reverse=True)
    return files[0] if files else None


def get_changelog(project_id, file_id):
    key = os.environ.get("CF_API_KEY")
    if not key:
        return None
    try:
        data = http_json(
            f"https://api.curseforge.com/v1/mods/{project_id}/files/{file_id}/changelog",
            headers={"x-api-key": key, "Accept": "application/json"})
    except Exception as e:
        print(f"  changelog alinamadi: {e}")
        return None
    html = (data or {}).get("data") or ""
    text = re.sub(r"<br\s*/?>|</p>|</li>|</h\d>", "\n", html, flags=re.I)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.I)
    text = unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:3500] + ("…" if len(text) > 3500 else "") if text else None


def post(webhook, project, f, changelog):
    title = project.get("title", "Addon")
    version = re.sub(r"\.zip$", "", f.get("display") or f.get("name") or "")
    desc = changelog or "Yeni sürüm CurseForge'da! / New version is out on CurseForge!"
    embed = {
        "title": f"🆕 {version}",
        "url": f.get("url"),
        "description": desc,
        "color": 0xC41E3A,
        "author": {"name": title, "url": (project.get("urls") or {}).get("curseforge")},
        "fields": [
            {"name": "Tür / Type", "value": f.get("type", "release"), "inline": True},
            {"name": "Oyun sürümü / Game version", "value": ", ".join(f.get("versions") or []) or "-", "inline": True},
            {"name": "İndir / Download", "value": f"[CurseForge]({f.get('url')})", "inline": True},
        ],
        "timestamp": f.get("uploaded_at"),
    }
    thumb = project.get("thumbnail")
    if thumb:
        embed["thumbnail"] = {"url": thumb}
    payload = {"username": "FallenSkullCorp Updates", "embeds": [embed]}
    role = os.environ.get("DISCORD_ROLE_ID")
    if role:
        payload["content"] = f"<@&{role}>"
        payload["allowed_mentions"] = {"roles": [role]}
    http_json(webhook, headers={"Content-Type": "application/json"},
              data=json.dumps(payload).encode(), method="POST")


def main():
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        sys.exit("DISCORD_WEBHOOK_URL tanimli degil.")
    addons = json.load(open(ADDONS_PATH, encoding="utf-8"))["addons"]
    state = json.load(open(STATE_PATH, encoding="utf-8")) if os.path.exists(STATE_PATH) else {}
    first_run = not state
    if os.environ.get("CF_API_KEY"):
        print("CF_API_KEY bulundu: resmi CurseForge API kullaniliyor")
    changed = False

    for slug in addons:
        print(f"- {slug}")
        project = get_project(slug)
        if not project:
            print("  proje okunamadi, atlandi")
            continue
        f = latest_file(project)
        if not f:
            continue
        if state.get(slug) == f["id"]:
            continue
        if first_run or slug not in state:
            # Ilk kez gorulen addon: duyurma, sadece kaydet (eski surumlerle spam olmasin)
            print(f"  kaydedildi: {f['display']}")
        else:
            print(f"  YENI: {f['display']} -> duyuruluyor")
            post(webhook, project, f, get_changelog(project["id"], f["id"]))
            time.sleep(2)
        state[slug] = f["id"]
        changed = True

    if changed:
        with open(STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
