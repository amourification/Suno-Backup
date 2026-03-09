"""
suno_backup.py — Main Suno Library Backup Tool
===============================================
Run via:  python setup_and_run.py   (recommended)
      or:  python suno_backup.py    (if deps already installed)

Supports:
  --scan-only           Run library scan only (write CSV/txt), no download.
  --from-csv PATH       Use existing suno_library.csv; skip scan.
  --song-ids-file PATH  Only download song IDs listed in this file (one ID per line).
  --rescan              Ignore existing CSV and run a full scan (CLI).
"""

import asyncio
import base64
import csv
import json
import os
import re
import sys
import time
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent.resolve()
sys.path.insert(0, str(HERE))

import requests
import requests.exceptions

try:
    from tqdm import tqdm
except ImportError:
    class tqdm:  # minimal shim
        def __init__(self, iterable=None, **kw): self._it = iterable or []
        def __iter__(self): return iter(self._it)
        def __enter__(self): return self
        def __exit__(self, *a): pass
        @staticmethod
        def write(s): print(s)

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed. Run setup_and_run.py first.")
    sys.exit(1)

import config as _cfg
from config import (
    SESSION_DIR, API_BASE, CDN_BASE, SUNO_ME,
    RATE_LIMIT_DL_MIN, RATE_LIMIT_DL_MAX,
    WAV_POLL_RETRIES, WAV_POLL_WAIT_MIN, WAV_POLL_WAIT_MAX,
    TOKEN_MAX_AGE_SEC, BROWSER_VIEWPORT, LOGIN_TIMEOUT_MS,
    SHORT_ID_LEN, EMBED_COVER_ART, CSV_FIELDS,
    resolve_output_dir,
)

# ── GUI config sidecar (written by gui.py before spawning this process) ───────
_GUI_CFG_PATH = HERE / ".gui_config.json"
if _GUI_CFG_PATH.exists():
    try:
        _gui = json.loads(_GUI_CFG_PATH.read_text())
        OUTPUT_DIR = resolve_output_dir(_gui.get("output_dir"), HERE)
        DOWNLOAD_MP3       = bool(_gui.get("download_mp3",   _cfg.DOWNLOAD_MP3))
        DOWNLOAD_WAV       = bool(_gui.get("download_wav",   _cfg.DOWNLOAD_WAV))
        DOWNLOAD_VIDEO     = bool(_gui.get("download_video", _cfg.DOWNLOAD_VIDEO))
        DOWNLOAD_ART       = bool(_gui.get("download_art",   _cfg.DOWNLOAD_ART))
        DOWNLOAD_JSON      = bool(_gui.get("download_json",  _cfg.DOWNLOAD_JSON))
        RATE_LIMIT_WAV_MIN = float(_gui.get("wav_delay_min", _cfg.RATE_LIMIT_WAV_MIN))
        RATE_LIMIT_WAV_MAX = float(_gui.get("wav_delay_max", _cfg.RATE_LIMIT_WAV_MAX))
    except Exception:
        OUTPUT_DIR = _cfg.OUTPUT_DIR
        DOWNLOAD_MP3 = _cfg.DOWNLOAD_MP3; DOWNLOAD_WAV = _cfg.DOWNLOAD_WAV
        DOWNLOAD_VIDEO = _cfg.DOWNLOAD_VIDEO; DOWNLOAD_ART = _cfg.DOWNLOAD_ART
        DOWNLOAD_JSON = _cfg.DOWNLOAD_JSON
        RATE_LIMIT_WAV_MIN = _cfg.RATE_LIMIT_WAV_MIN
        RATE_LIMIT_WAV_MAX = _cfg.RATE_LIMIT_WAV_MAX
else:
    OUTPUT_DIR = _cfg.OUTPUT_DIR
    DOWNLOAD_MP3 = _cfg.DOWNLOAD_MP3; DOWNLOAD_WAV = _cfg.DOWNLOAD_WAV
    DOWNLOAD_VIDEO = _cfg.DOWNLOAD_VIDEO; DOWNLOAD_ART = _cfg.DOWNLOAD_ART
    DOWNLOAD_JSON = _cfg.DOWNLOAD_JSON
    RATE_LIMIT_WAV_MIN = _cfg.RATE_LIMIT_WAV_MIN
    RATE_LIMIT_WAV_MAX = _cfg.RATE_LIMIT_WAV_MAX

from vault   import save_tokens, load_tokens, is_token_fresh
from scanner import full_library_scan

# When set by the GUI, skip interactive prompts and proceed with download.
# Also skip when stdin is not a TTY (e.g. piped from GUI) so we never block on input().
GUI_MODE = (
    os.environ.get("SUNO_GUI_MODE") == "1"
    or not sys.stdin.isatty()
)

# ── Backup log (traceability / database-style logging) ───────────────────────
# Session log: one file per run in OUTPUT_DIR/logs/. Also append to backup.log.
_session_log_path: Path | None = None

def _backup_log_path() -> Path:
    return OUTPUT_DIR / "backup.log"

def _logs_dir() -> Path:
    return OUTPUT_DIR / "logs"

def backup_log(event: str, song_id: str | None = None, detail: str | None = None, **kwargs) -> None:
    """Append one line to the current session log (if set) and to backup.log.
    Format: ISO timestamp, event, song_id, detail, and optional key=value pairs."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts = [ts, "BACKUP", event]
    if song_id:
        parts.append(f"song_id={song_id}")
    if detail:
        parts.append(detail)
    for k, v in kwargs.items():
        if v is not None and v != "":
            parts.append(f"{k}={v}")
    line = "  ".join(str(p) for p in parts) + "\n"
    # Session log (one file per run in logs folder)
    global _session_log_path
    if _session_log_path is not None:
        try:
            with open(_session_log_path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass
    # Cumulative backup.log
    try:
        log_path = _backup_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        print(f"  ⚠ Could not write backup.log: {e}", file=sys.stderr)

# ── Load from existing CSV (skip scan) ─────────────────────────────────────────

def load_songs_from_csv(csv_path: Path, song_ids: list[str] | None = None) -> list[dict]:
    """Load song list from an existing suno_library.csv. Optionally filter by song_ids.
    Ensures every row has all CSV_FIELDS keys (missing ones set to '')."""
    if not csv_path.exists():
        return []
    songs: list[dict] = []
    want_ids = set((song_ids or []))
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = (row.get("id") or "").strip()
            if not sid:
                continue
            if want_ids and sid not in want_ids:
                continue
            for key in CSV_FIELDS:
                if key not in row:
                    row[key] = ""
            songs.append(row)
    return songs


def load_song_ids_from_file(path: Path) -> list[str]:
    """Load song IDs from a file (one ID per line)."""
    if not path.exists():
        return []
    ids = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            ids.append(line)
    return ids

# ── Helpers ───────────────────────────────────────────────────────────────────

def _jitter(lo: float, hi: float) -> None:
    time.sleep(random.uniform(lo, hi))


def sanitize(name: str, max_len: int = 80) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", str(name))
    name = re.sub(r'\s+', "_", name.strip())
    return name[:max_len] or "untitled"


def song_folder(song: dict) -> Path:
    sid   = song.get("id", "unknown")
    title = sanitize(song.get("title") or song.get("display_name") or sid)
    if SHORT_ID_LEN and isinstance(SHORT_ID_LEN, int) and SHORT_ID_LEN > 0:
        short_id = (sid.replace("-", "")[:SHORT_ID_LEN]) if sid else "unknown"
        name = f"{title}__{short_id}"
    else:
        name = f"{title}__{sid}"
    d = OUTPUT_DIR / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def file_exists(folder: Path, ext: str) -> bool:
    return any(folder.glob(f"*.{ext}"))


def get_song_status(folder: Path) -> dict:
    """Inspect folder and return has_mp3, has_wav, has_video, has_metadata, has_cover (each '1' or '0')."""
    return {
        "has_mp3":      "1" if file_exists(folder, "mp3") else "0",
        "has_wav":      "1" if file_exists(folder, "wav") else "0",
        "has_video":    "1" if (file_exists(folder, "mp4") or file_exists(folder, "webm")) else "0",
        "has_metadata": "1" if (folder / "metadata.json").exists() else "0",
        "has_cover":    "1" if (file_exists(folder, "jpg") or file_exists(folder, "jpeg")) else "0",
    }


def write_library_csv(songs: list[dict], csv_path: Path) -> None:
    """Write full library CSV with all CSV_FIELDS. Used to persist status after each song."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in songs:
            out = {k: row.get(k, "") for k in CSV_FIELDS}
            writer.writerow(out)


def refresh_csv_status_from_disk(songs: list[dict], csv_path: Path) -> None:
    """Update each song row's has_mp3, has_wav, etc. from disk and write CSV."""
    for song in songs:
        folder = song_folder(song)
        status = get_song_status(folder)
        song.update(status)
        if any(song.get(k) == "1" for k in ("has_mp3", "has_wav", "has_video", "has_metadata", "has_cover")):
            song["last_updated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_library_csv(songs, csv_path)


def download_file(url: str, dest: Path, auth_headers: dict | None = None) -> bool:
    h = {"accept": "*/*", "referer": "https://suno.com/"}
    if auth_headers:
        h.update(auth_headers)
    try:
        r = requests.get(url, headers=h, stream=True, timeout=90)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 17):
                f.write(chunk)
        _jitter(RATE_LIMIT_DL_MIN, RATE_LIMIT_DL_MAX)
        return True
    except requests.exceptions.HTTPError as exc:
        tqdm.write(f"      ✗ HTTP {exc.response.status_code}: {url}")
        return False
    except requests.exceptions.RequestException as exc:
        tqdm.write(f"      ✗ Network error: {exc}")
        return False


def download_cdn_file(url: str, dest: Path, *, on_403_message: str | None = None) -> bool:
    """Download from cdn1.suno.ai. Browser does NOT send auth to CDN — only origin + referer."""
    h = {
        "accept": "*/*",
        "referer": "https://suno.com/",
        "origin": "https://suno.com",
    }
    try:
        r = requests.get(url, headers=h, stream=True, timeout=90)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 17):
                f.write(chunk)
        _jitter(RATE_LIMIT_DL_MIN, RATE_LIMIT_DL_MAX)
        return True
    except requests.exceptions.HTTPError as exc:
        if exc.response.status_code == 403 and on_403_message is not None:
            tqdm.write(on_403_message)
        else:
            tqdm.write(f"      ✗ HTTP {exc.response.status_code}: {url}")
        return False
    except requests.exceptions.RequestException as exc:
        tqdm.write(f"      ✗ Network error: {exc}")
        return False

# ── Auth ──────────────────────────────────────────────────────────────────────

async def _capture_tokens(page) -> dict:
    captured: dict = {}

    async def on_req(req):
        if "studio-api.prod.suno.com" in req.url:
            h = req.headers
            if "authorization" in h:
                captured["authorization"] = h["authorization"]
            if "browser-token" in h:
                captured["browser-token"] = h["browser-token"]

    page.on("request", on_req)
    # Load once so requests happen with our listener attached; then wait only (no reloads).
    await page.goto(SUNO_ME, wait_until="networkidle", timeout=60_000)

    # Wait up to 2 minutes for an auth request, checking every 5s. No reloads — let the user log in if needed.
    for _ in range(24):
        await page.wait_for_timeout(5_000)
        if captured.get("authorization"):
            break
        print("  ⏳ Waiting for auth… (log in in the browser if needed)")

    page.remove_listener("request", on_req)

    if not captured.get("authorization"):
        raise RuntimeError(
            "Could not capture auth headers.\n"
            "  → Make sure you're logged in and the Suno library page has fully loaded.\n"
            "  → Try again; if it keeps failing, use 'Clear Vault' and log in again."
        )
    captured["_saved_at"] = time.time()
    return captured


async def get_auth_headers() -> dict:
    saved = load_tokens()
    if saved and is_token_fresh(saved):
        print("  ✓ Using cached tokens from encrypted vault")
        return {k: v for k, v in saved.items() if not k.startswith("_")}

    print("  " + ("⚠  Cached tokens are stale — refreshing..." if saved
                  else "ℹ  No cached tokens — launching browser for login..."))

    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=False,
            viewport=BROWSER_VIEWPORT,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto(SUNO_ME, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(2_000)

        if re.search(r"sign[-_]in|login|auth", page.url, re.I):
            print("\n  🔐 Please log in to Suno in the browser window.")
            print(f"     Waiting up to {LOGIN_TIMEOUT_MS // 60000} minutes...\n")
            await page.wait_for_url(re.compile(r"suno\.com/(?!.*sign)"),
                                    timeout=LOGIN_TIMEOUT_MS)
            await page.wait_for_timeout(3_000)
            print("  ✓ Login detected!\n")
        else:
            print("  ✓ Already logged in (saved session)\n")

        tokens = await _capture_tokens(page)
        await browser.close()

    save_tokens(tokens)
    return {k: v for k, v in tokens.items() if not k.startswith("_")}

# ── WAV ───────────────────────────────────────────────────────────────────────
# Site flow: 3-dots → Download → choose WAV → popup "preparing" → download button.
# We mirror: POST convert_wav (= choose WAV) → GET wav_file until 200 (= button ready)
#            → use response body if it's the file, else GET from CDN URL.

# One device-id per run (browser sends same value for all WAV/API requests)
_DEVICE_ID: str | None = None


def _fresh_api_headers(hdrs: dict) -> dict:
    """Return a copy of hdrs with browser-token refreshed and device-id set (API expects both)."""
    global _DEVICE_ID
    out = dict(hdrs)
    try:
        ts = int(time.time() * 1000)
        inner = json.dumps({"timestamp": ts})
        token_b64 = base64.standard_b64encode(inner.encode()).decode()
        out["browser-token"] = json.dumps({"token": token_b64})
    except Exception:
        pass
    if _DEVICE_ID is None:
        _DEVICE_ID = str(uuid.uuid4())
    out["device-id"] = _DEVICE_ID
    return out


def _wav_convert(song_id: str, hdrs: dict) -> bool:
    api_hdrs = _fresh_api_headers(hdrs)
    try:
        r = requests.post(
            f"{API_BASE}/api/gen/{song_id}/convert_wav/",
            headers=api_hdrs,
            timeout=30,
        )
        if r.status_code == 429:
            tqdm.write("      ⚠  Rate-limited on convert_wav, pausing 20 s")
            time.sleep(20)
            return False
        if r.status_code in (200, 201, 202, 204):
            tqdm.write("      ✓ convert_wav OK")
            return True
        tqdm.write(f"      ✗ convert_wav → {r.status_code} (WAV may require Pro)")
        return False
    except requests.exceptions.RequestException as exc:
        tqdm.write(f"      ✗ convert_wav: {exc}")
        return False


def _wav_wait(song_id: str, hdrs: dict) -> tuple[bool, str | None, bytes | None]:
    """Poll wav_file until ready. Returns (success, download_url_or_none, response_body_or_none).
    When 200: if response is the file (binary), body is set; else if JSON with url, download_url is set."""
    url = f"{API_BASE}/api/gen/{song_id}/wav_file/"
    for i in range(WAV_POLL_RETRIES):
        api_hdrs = _fresh_api_headers(hdrs)
        try:
            r = requests.get(url, headers=api_hdrs, timeout=30)
            if r.status_code == 200:
                tqdm.write("      ✓ wav_file ready")
                ct = (r.headers.get("content-type") or "").lower()
                # Response may be the file itself (e.g. after redirect or direct)
                if "audio" in ct or "octet-stream" in ct or (len(r.content) > 1000 and not ct.startswith("application/json")):
                    return (True, None, r.content)
                if ct.startswith("application/json"):
                    try:
                        data = r.json()
                        download_url = (
                            data.get("url") or data.get("download_url")
                            or data.get("file_url") or data.get("file") or data.get("wav_url") or ""
                        )
                        if isinstance(download_url, str):
                            download_url = download_url.strip()
                        else:
                            download_url = ""
                        if download_url:
                            return (True, download_url, None)
                    except Exception:
                        pass
                # Redirect: final URL might be CDN (requests follows redirects; content may be the file)
                if r.url and r.url != url and len(r.content) > 1000:
                    return (True, None, r.content)
                return (True, None, None)
            if r.status_code == 202:
                wait = random.uniform(WAV_POLL_WAIT_MIN, WAV_POLL_WAIT_MAX)
                tqdm.write(f"      ⏳ WAV processing ({i+1}/{WAV_POLL_RETRIES}, "
                           f"retry in {wait:.1f}s)...")
                time.sleep(wait)
                continue
            tqdm.write(f"      ✗ wav_file → {r.status_code}")
            return (False, None, None)
        except requests.exceptions.RequestException as exc:
            tqdm.write(f"      ✗ wav_file: {exc}")
            time.sleep(random.uniform(WAV_POLL_WAIT_MIN, WAV_POLL_WAIT_MAX))
    tqdm.write("      ✗ wav_file timeout")
    return (False, None, None)


def download_wav(song_id: str, hdrs: dict, dest: Path) -> bool:
    if not _wav_convert(song_id, hdrs):
        return False
    ok_wait, download_url, body = _wav_wait(song_id, hdrs)
    if not ok_wait:
        return False
    # If API returned the file in the response body (site logic: "download" = same response), save it
    if body and len(body) > 0:
        try:
            dest.write_bytes(body)
            tqdm.write("      ✓ WAV downloaded (from API response)")
            _jitter(RATE_LIMIT_WAV_MIN, RATE_LIMIT_WAV_MAX)
            return True
        except OSError as e:
            tqdm.write(f"      ✗ WAV save: {e}")
            return False
    # Else fetch from URL (from API JSON or default CDN path)
    cdn_url = download_url or f"{CDN_BASE}/{song_id}.wav"
    ok = download_cdn_file(cdn_url, dest)
    if ok:
        tqdm.write("      ✓ WAV downloaded")
    _jitter(RATE_LIMIT_WAV_MIN, RATE_LIMIT_WAV_MAX)
    return ok

# ── Video (MP4) ───────────────────────────────────────────────────────────────
# Site flow: like WAV, video may need a "prepare" call before CDN allows the request.
# DevTools: POST /api/billing/clips/{id}/download/ (200) then GET cdn1.suno.ai/{id}.mp4

def _video_prepare(song_id: str, hdrs: dict) -> bool:
    """Register video download with billing API so CDN allows the request (avoids 403)."""
    api_hdrs = _fresh_api_headers(hdrs)
    try:
        r = requests.post(
            f"{API_BASE}/api/billing/clips/{song_id}/download/",
            headers=api_hdrs,
            timeout=30,
        )
        if r.status_code in (200, 201, 202, 204):
            return True
        if r.status_code == 429:
            time.sleep(20)
            return False
        return False
    except requests.exceptions.RequestException:
        return False


def download_video(song_id: str, hdrs: dict, dest: Path) -> bool:
    if not _video_prepare(song_id, hdrs):
        pass  # Try CDN anyway; some tracks may work without prepare
    time.sleep(1)  # Brief delay so CDN sees the prepare
    return download_cdn_file(
        f"{CDN_BASE}/{song_id}.mp4",
        dest,
        on_403_message="      ✗ Video 403 (skipped)",
    )

# ── Per-song backup ───────────────────────────────────────────────────────────
# Old logic: one song at a time, order json → art → mp3 → wav → video → embed.
# Folders are created in a separate pass before downloads to avoid mixing I/O.

def backup_song(song: dict, hdrs: dict, stats: dict) -> None:
    sid    = song.get("id", "unknown")
    title  = song.get("title") or song.get("display_name") or sid
    folder = song_folder(song)

    tqdm.write(f"\n  ♪ {title}  [{sid}]")
    backup_log("song_start", song_id=sid, title=title[:80])

    if DOWNLOAD_JSON:
        p = folder / "metadata.json"
        if not p.exists():
            p.write_text(json.dumps(song, indent=2, ensure_ascii=False))
            stats["json"] += 1
            backup_log("metadata_written", song_id=sid, path=str(p))

    if DOWNLOAD_ART and not file_exists(folder, "jpg") and not file_exists(folder, "jpeg"):
        art_url = (song.get("image_large_url") or song.get("image_url")
                   or f"{CDN_BASE}/image_{sid}.jpeg")
        tqdm.write("    → Cover art...")
        dest_art = folder / f"image_{sid}.jpeg"
        if download_file(art_url, dest_art):
            stats["art"] += 1
            backup_log("art_downloaded", song_id=sid, path=str(dest_art))
        else:
            backup_log("art_failed", song_id=sid, detail="download failed")

    if DOWNLOAD_MP3 and not file_exists(folder, "mp3"):
        url = song.get("audio_url") or song.get("mp3_url")
        if url:
            tqdm.write("    → MP3...")
            dest_mp3 = folder / f"{sanitize(title)}.mp3"
            if download_file(url, dest_mp3, hdrs):
                stats["mp3"] += 1
                backup_log("mp3_downloaded", song_id=sid, path=str(dest_mp3))
            else:
                stats["mp3_fail"] += 1
                backup_log("mp3_failed", song_id=sid, detail="download failed")

    if DOWNLOAD_WAV and not file_exists(folder, "wav"):
        tqdm.write("    → WAV (convert + download)...")
        dest_wav = folder / f"{sanitize(title)}.wav"
        if download_wav(sid, hdrs, dest_wav):
            stats["wav"] += 1
            backup_log("wav_downloaded", song_id=sid, path=str(dest_wav))
        else:
            stats["wav_fail"] += 1
            backup_log("wav_failed", song_id=sid, detail="convert or download failed")

    if DOWNLOAD_VIDEO and not file_exists(folder, "webm") and not file_exists(folder, "mp4"):
        tqdm.write("    → Video (MP4)...")
        dest_video = folder / f"{sanitize(title)}.mp4"
        if download_video(sid, hdrs, dest_video):
            stats["video"] += 1
            backup_log("video_downloaded", song_id=sid, path=str(dest_video))
        else:
            stats["video_fail"] += 1
            backup_log("video_failed", song_id=sid, detail="download failed or 403")

    if EMBED_COVER_ART:
        _embed_cover_art(folder, sid, title)
        if file_exists(folder, "mp3") or file_exists(folder, "wav"):
            backup_log("cover_embedded", song_id=sid)


def _embed_cover_art(folder: Path, sid: str, title: str) -> None:
    """Embed folder's cover image into MP3 and WAV (ID3 APIC). Requires mutagen."""
    cover_path = folder / f"image_{sid}.jpeg"
    if not cover_path.exists():
        cover_path = next((p for p in folder.glob("image_*") if p.suffix.lower() in (".jpg", ".jpeg")), None)
    if not cover_path or not cover_path.exists():
        return
    try:
        image_data = cover_path.read_bytes()
    except OSError:
        return
    mime = "image/jpeg" if cover_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"

    try:
        from mutagen.id3 import ID3, APIC
        from mutagen.wave import WAVE
    except ImportError:
        return

    def add_apic(audio_path: Path) -> bool:
        try:
            if audio_path.suffix.lower() == ".mp3":
                try:
                    audio = ID3(str(audio_path))
                except Exception:
                    audio = ID3()
                audio.delall("APIC")
                audio.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=image_data))
                audio.save(str(audio_path), v2_version=3)
                return True
            if audio_path.suffix.lower() == ".wav":
                try:
                    w = WAVE(str(audio_path))
                    if w.tags is None:
                        w.add_tags()
                    if hasattr(w.tags, "add") and hasattr(w.tags, "save"):
                        w.tags.delall("APIC")
                        w.tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=image_data))
                        w.save()
                        return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    for ext in ("mp3", "wav"):
        for p in folder.glob(f"*.{ext}"):
            if add_apic(p):
                tqdm.write(f"    → Embedded cover in {p.name}")

def _parse_args() -> tuple[Path | None, Path | None, bool]:
    """Return (from_csv_path, song_ids_file_path, rescan)."""
    args = sys.argv[1:]
    from_csv = None
    song_ids_file = None
    rescan = False
    i = 0
    while i < len(args):
        if args[i] == "--from-csv" and i + 1 < len(args):
            from_csv = Path(args[i + 1]).resolve()
            i += 2
        elif args[i] == "--song-ids-file" and i + 1 < len(args):
            song_ids_file = Path(args[i + 1]).resolve()
            i += 2
        elif args[i] == "--rescan":
            rescan = True
            i += 1
        else:
            i += 1
    return (from_csv, song_ids_file, rescan)


def _default_csv_path() -> Path:
    """Path to default library CSV in output dir."""
    return OUTPUT_DIR / "suno_library.csv"


async def main():
    print("=" * 60)
    print("  SUNO LIBRARY BACKUP TOOL v2")
    print("=" * 60 + "\n")

    global _session_log_path
    logs_dir = _logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    _session_log_path = logs_dir / f"session_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S')}.log"
    try:
        _session_log_path.write_text(
            f"# Suno Backup session log  {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
            f"# Output dir: {OUTPUT_DIR}\n"
            f"# Format: TIMESTAMP  BACKUP  EVENT  [song_id=...]  [key=value...]\n"
            f"# ---\n",
            encoding="utf-8",
        )
    except OSError:
        pass

    from_csv_path, song_ids_file_path, rescan = _parse_args()
    scan_only = "--scan-only" in sys.argv
    backup_log("run_start", mode="scan_only" if scan_only else "download", output_dir=str(OUTPUT_DIR), session_log=str(_session_log_path))

    # --scan-only: always run a full scan, never load from existing CSV
    if scan_only:
        from_csv_path = None
    elif not rescan and from_csv_path is None and _default_csv_path().exists():
        # CLI: reuse previous scan when CSV exists
        from_csv_path = _default_csv_path()

    print("🔑 Getting auth tokens...")
    auth_hdrs = await get_auth_headers()

    if from_csv_path:
        # Use existing scan: load from CSV, optionally filter by song IDs file
        print("\n📂 Loading library from previous scan...")
        print(f"   CSV: {from_csv_path}")
        want_ids = load_song_ids_from_file(song_ids_file_path) if song_ids_file_path else None
        if want_ids:
            print(f"   Selected: {len(want_ids)} songs")
        # Always load full CSV so we can refresh and write back without losing rows
        full_songs = load_songs_from_csv(from_csv_path, song_ids=None)
        if not full_songs:
            print("\n⚠  No songs found in CSV. Run a scan first.")
            backup_log("session_end", detail="no_songs_in_csv")
            return
        refresh_csv_status_from_disk(full_songs, from_csv_path)
        backup_log("csv_loaded_and_refreshed", song_count=len(full_songs), csv=str(from_csv_path))
        songs = full_songs if not want_ids else [s for s in full_songs if (s.get("id") or "").strip() in set(want_ids)]
        if want_ids and not songs:
            print("\n⚠  No matching songs in CSV for the given IDs.")
            backup_log("session_end", detail="no_matching_song_ids")
            return
        print(f"\n✓ {len(songs)} songs to process")

        # CLI interactive: offer to filter by file if not already using one (skip in GUI mode)
        if not GUI_MODE and not song_ids_file_path and songs:
            try:
                ans = input("\n  Download (a)ll or (f)rom file? [a]: ").strip().lower() or "a"
                if ans == "f":
                    path_str = input("  Path to file with song IDs (one per line): ").strip()
                    if path_str:
                        song_ids_file_path = Path(path_str).resolve()
                        want_ids = load_song_ids_from_file(song_ids_file_path)
                        if want_ids:
                            songs = load_songs_from_csv(from_csv_path, song_ids=want_ids)
                            print(f"  → {len(songs)} songs selected from file")
                        else:
                            print("  ⚠  No valid IDs in file. Downloading all.")
            except EOFError:
                pass
    else:
        # Full scan
        print("\n🔎 Running full library scan...")
        raw_songs = await full_library_scan(auth_hdrs, OUTPUT_DIR)
        if not raw_songs:
            print("\n⚠  No songs found.")
            backup_log("session_end", detail="no_songs_from_scan")
            return
        print(f"\n✓ {len(raw_songs)} songs indexed → {OUTPUT_DIR / 'suno_library.csv'}")
        backup_log("scan_exported", song_count=len(raw_songs), csv=str(_default_csv_path()))
        # Load as row dicts so we have CSV_FIELDS and can update status
        songs = load_songs_from_csv(_default_csv_path())
        if not songs:
            songs = raw_songs  # fallback if CSV not readable
        # Refresh has_mp3, has_wav, etc. from existing files on disk and rewrite CSV
        csv_path_scan = _default_csv_path()
        refresh_csv_status_from_disk(songs, csv_path_scan)
        backup_log("scan_csv_refreshed", song_count=len(songs), csv=str(csv_path_scan))
        full_songs = songs

    if scan_only:
        print("  Scan-only mode: skipping download.")
        backup_log("scan_only_complete", song_count=len(songs), csv=str(_default_csv_path()))
        backup_log("session_end", mode="scan_only")
        if _session_log_path is not None:
            print(f"  Session log : {_session_log_path}")
        return

    if not from_csv_path:
        full_songs = songs

    if GUI_MODE:
        ans = "y"
    else:
        try:
            ans = input(f"\n  Download files for {len(songs)} songs? [Y/n]: ").strip().lower()
        except EOFError:
            ans = "y"
    if ans not in ("", "y", "yes"):
        print("  Download skipped.")
        backup_log("session_end", detail="download_skipped_by_user")
        return

    csv_path = from_csv_path if from_csv_path else _default_csv_path()
    backup_log("download_run_start", song_count=len(songs), csv=str(csv_path))

    stats = dict(mp3=0, mp3_fail=0, wav=0, wav_fail=0,
                 video=0, video_fail=0, art=0, json=0)
    last_refresh = time.time()

    for i, song in enumerate(tqdm(songs, desc="Downloading", unit="song")):
        # Proactive token refresh before expiry
        if time.time() - last_refresh > TOKEN_MAX_AGE_SEC - 300:
            tqdm.write("\n  ⚠  Refreshing tokens proactively...")
            try:
                auth_hdrs   = await get_auth_headers()
                last_refresh = time.time()
            except Exception as exc:
                tqdm.write(f"  ⚠  Token refresh failed: {exc}")

        backup_song(song, auth_hdrs, stats)

        # Update CSV from disk and persist after each download (tracks what was downloaded)
        folder = song_folder(song)
        status = get_song_status(folder)
        song.update(status)
        song["last_updated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        write_library_csv(full_songs, csv_path)
        backup_log(
            "csv_updated",
            song_id=song.get("id"),
            has_mp3=status["has_mp3"],
            has_wav=status["has_wav"],
            has_video=status["has_video"],
            has_metadata=status["has_metadata"],
            has_cover=status["has_cover"],
        )
        backup_log(
            "song_download_complete",
            song_id=song.get("id"),
            detail="CSV written",
            has_mp3=status["has_mp3"],
            has_wav=status["has_wav"],
            has_video=status["has_video"],
        )

    backup_log(
        "download_run_complete",
        songs=len(songs),
        mp3=stats["mp3"], mp3_fail=stats["mp3_fail"],
        wav=stats["wav"], wav_fail=stats["wav_fail"],
        video=stats["video"], video_fail=stats["video_fail"],
        art=stats["art"], json=stats["json"],
    )
    backup_log("session_end", mode="download", songs=len(songs))
    print("\n" + "═" * 60)
    print("  BACKUP COMPLETE")
    print("═" * 60)
    print(f"  Songs    : {len(songs)}")
    print(f"  MP3   ✓ {stats['mp3']:>4}  ✗ {stats['mp3_fail']}")
    print(f"  WAV   ✓ {stats['wav']:>4}  ✗ {stats['wav_fail']}")
    print(f"  Video ✓ {stats['video']:>4}  ✗ {stats['video_fail']}")
    print(f"  Art   ✓ {stats['art']:>4}  JSON ✓ {stats['json']}")
    print(f"  Output   : {OUTPUT_DIR.resolve()}")
    if _session_log_path is not None:
        print(f"  Session log : {_session_log_path}")
    print("═" * 60)


if __name__ == "__main__":
    asyncio.run(main())
