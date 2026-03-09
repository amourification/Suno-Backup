"""
scanner.py — Full library scanner & CSV exporter
==================================================
Three-phase scan:
  1. /api/feed/v2/           — paginated personal feed
  2. DOM scraping            — Playwright extracts IDs from page source
     (image_{id}.jpeg, {id}.webm, /song/{id}, embedded JSON, etc.)
  3. /api/get_songs_by_ids   — batch-enriches IDs found only in DOM

Outputs:
  suno_library/suno_library.csv  — full library index
  suno_library/song_ids.txt      — plain ID list
"""

import csv
import random
import re
import time
import unicodedata
from pathlib import Path

import requests
import requests.exceptions

try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False

from config import (
    API_BASE, CDN_BASE, SESSION_DIR,
    PAGE_SIZE, BATCH_SIZE, CSV_FIELDS,
    RATE_LIMIT_PAGE_MIN, RATE_LIMIT_PAGE_MAX,
    RATE_LIMIT_BATCH_MIN, RATE_LIMIT_BATCH_MAX,
    BROWSER_VIEWPORT,
)

# ── Jittered sleep helpers ────────────────────────────────────────────────────

def _jitter(lo: float, hi: float) -> None:
    """Sleep for a random duration in [lo, hi] seconds."""
    time.sleep(random.uniform(lo, hi))

# ── Auth header builder ───────────────────────────────────────────────────────

def _auth_headers(auth_headers: dict) -> dict:
    return {
        "accept":          "*/*",
        "accept-language": "en-US,en;q=0.9",
        **auth_headers,
    }

# ── API feed pagination ───────────────────────────────────────────────────────

def fetch_feed_page(page_num: int, auth_headers: dict) -> list[dict]:
    """Fetch one page of the personal feed; raises on auth failure."""
    url = f"{API_BASE}/api/feed/v2/?page={page_num}&page_size={PAGE_SIZE}"
    try:
        r = requests.get(url, headers=_auth_headers(auth_headers), timeout=30)
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"Network error fetching page {page_num}: {exc}") from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(f"Timeout fetching page {page_num}: {exc}") from exc

    if r.status_code == 401:
        raise RuntimeError("Auth token expired — re-run to refresh.")
    if r.status_code == 429:
        raise RuntimeError("Rate-limited by Suno API. Wait a few minutes and retry.")
    r.raise_for_status()

    data = r.json()
    return data.get("clips") or data.get("songs") or data.get("data") or []


def fetch_songs_by_ids(ids: list[str], auth_headers: dict) -> list[dict]:
    """Batch-enrich up to BATCH_SIZE IDs per request via get_songs_by_ids."""
    results: list[dict] = []
    for i in range(0, len(ids), BATCH_SIZE):
        batch  = ids[i: i + BATCH_SIZE]
        id_str = ",".join(batch)
        url    = f"{API_BASE}/api/get_songs_by_ids?ids={id_str}"
        try:
            r = requests.get(url, headers=_auth_headers(auth_headers), timeout=30)
            if r.status_code == 200:
                data  = r.json()
                songs = (data.get("clips") or data.get("songs")
                         or (data if isinstance(data, list) else []))
                results.extend(songs)
            elif r.status_code == 429:
                print(f"    ⚠  Rate-limited on batch {i // BATCH_SIZE + 1}; pausing 15 s")
                time.sleep(15)
            else:
                print(f"    ⚠  get_songs_by_ids → {r.status_code} (batch {i // BATCH_SIZE + 1})")
        except requests.exceptions.RequestException as exc:
            print(f"    ⚠  Network error on batch {i // BATCH_SIZE + 1}: {exc}")

        _jitter(RATE_LIMIT_BATCH_MIN, RATE_LIMIT_BATCH_MAX)

    return results

# ── DOM scraping ──────────────────────────────────────────────────────────────

_UUID_RE = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

_ID_PATTERNS = [
    re.compile(rf"image_({_UUID_RE})\.jpe?g",             re.I),
    re.compile(rf"({_UUID_RE})\.webm",                    re.I),
    re.compile(rf"({_UUID_RE})\.mp3",                     re.I),
    re.compile(rf"({_UUID_RE})\.wav",                     re.I),
    re.compile(rf"/song/({_UUID_RE})",                    re.I),
    re.compile(rf'"id"\s*:\s*"({_UUID_RE})"',             re.I),
]


def _extract_ids_from_html(html: str) -> set[str]:
    """Extract all song UUIDs visible anywhere in a page's HTML source."""
    found: set[str] = set()
    for pat in _ID_PATTERNS:
        for m in pat.finditer(html):
            found.add(m.group(1).lower())
    return found


async def _scrape_page_ids(page: Page, url: str) -> set[str]:
    await page.goto(url, wait_until="networkidle", timeout=60_000)
    await page.wait_for_timeout(2_000)
    for _ in range(6):
        await page.keyboard.press("End")
        await page.wait_for_timeout(700)
    return _extract_ids_from_html(await page.content())


async def scrape_all_ids_from_dom(auth_headers: dict) -> set[str]:  # noqa: ARG001
    if not PLAYWRIGHT_OK:
        print("  ⚠  Playwright not available, skipping DOM scrape")
        return set()

    all_ids: set[str] = set()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=True,
            viewport=BROWSER_VIEWPORT,
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()

        for url in (
            "https://suno.com/me",
            "https://suno.com/me?tab=songs",
            "https://suno.com/me?tab=liked",
        ):
            print(f"    Scanning DOM: {url}")
            try:
                ids = await _scrape_page_ids(page, url)
                print(f"      Found {len(ids)} IDs")
                all_ids.update(ids)
            except Exception as exc:  # broad OK — DOM scrape is best-effort
                print(f"      ⚠  {exc}")

        await browser.close()

    return all_ids

# ── CSV / ID-list export ──────────────────────────────────────────────────────

def _normalize_text(s: str) -> str:
    """Normalise Unicode to NFC so Arabic and other scripts display correctly."""
    if not s or not isinstance(s, str):
        return s
    return unicodedata.normalize("NFC", s)


def _flatten_song(song: dict) -> dict:
    """Normalise a raw API song dict into a flat CSV row."""
    def g(*keys):
        for k in keys:
            v = song.get(k)
            if v is not None and v != "":
                return v
        return ""

    meta = song.get("metadata") or {}
    sid  = g("id")

    return {
        "id":              sid,
        "title":           _normalize_text(g("title", "display_name")),
        "display_name":    _normalize_text(g("display_name", "title")),
        "status":          g("status"),
        "duration":        g("duration"),
        "created_at":      g("created_at", "created_at_str"),
        "audio_url":       g("audio_url", "mp3_url"),
        "wav_url":         f"{CDN_BASE}/{sid}.wav"          if sid else "",
        "video_url":       g("video_url") or (f"{CDN_BASE}/{sid}.webm" if sid else ""),
        "image_url":       g("image_url"),
        "image_large_url": g("image_large_url") or (f"{CDN_BASE}/image_{sid}.jpeg" if sid else ""),
        "model_name":      g("model_name", "model"),
        "tags":            _normalize_text(g("tags")   or meta.get("tags",            "")),
        "prompt":          _normalize_text(g("prompt") or meta.get("prompt",          "")),
        "style":           _normalize_text(g("style")  or meta.get("style_of_music",  "")),
        "is_public":       g("is_public"),
        "play_count":      g("play_count"),
        "upvote_count":    g("upvote_count"),
        "source":          song.get("_source", "api"),
        "has_mp3":         "0",
        "has_wav":         "0",
        "has_video":       "0",
        "has_metadata":    "0",
        "has_cover":       "0",
        "last_updated_utc": "",
    }


def export_csv(songs: list[dict], output_path: Path) -> int:
    """Write deduplicated songs to CSV. Returns number of rows."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    seen: dict[str, dict] = {}
    for song in songs:
        row = _flatten_song(song)
        sid = row["id"]
        if sid not in seen or row.get("audio_url"):
            seen[sid] = row

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(seen.values())

    return len(seen)


def export_id_list(song_ids: list[str], output_path: Path) -> None:
    output_path.write_text("\n".join(sorted(set(song_ids))) + "\n")

# ── Main scan orchestrator ────────────────────────────────────────────────────

async def full_library_scan(auth_headers: dict, output_dir: Path) -> list[dict]:
    """Run all three phases. Returns deduplicated list of song dicts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    all_songs: dict[str, dict] = {}

    # Phase 1 — API feed
    print("\n📡 Phase 1: Scanning API feed pages...")
    page_num = 0
    while True:
        try:
            batch = fetch_feed_page(page_num, auth_headers)
        except RuntimeError as exc:
            print(f"  ⚠  {exc}")
            break

        if not batch:
            break

        for s in batch:
            sid = s.get("id")
            if sid:
                s["_source"] = "api_feed"
                all_songs[sid] = s

        print(f"  Page {page_num + 1}: {len(batch)} songs | Total: {len(all_songs)}")

        if len(batch) < PAGE_SIZE:
            break
        page_num += 1
        _jitter(RATE_LIMIT_PAGE_MIN, RATE_LIMIT_PAGE_MAX)

    print(f"  ✓ Feed complete: {len(all_songs)} songs")

    # Phase 2 — DOM scrape
    print("\n🌐 Phase 2: DOM scraping for additional IDs...")
    dom_ids = await scrape_all_ids_from_dom(auth_headers)
    new_ids = dom_ids - set(all_songs.keys())
    print(f"  DOM: {len(dom_ids)} total IDs, {len(new_ids)} new")

    # Phase 3 — Enrich new IDs
    if new_ids:
        print(f"\n🔍 Phase 3: Enriching {len(new_ids)} new IDs...")
        enriched = fetch_songs_by_ids(list(new_ids), auth_headers)
        for s in enriched:
            sid = s.get("id")
            if sid:
                s["_source"] = "dom_scan+api_enrich"
                all_songs[sid] = s
        returned = {s.get("id") for s in enriched}
        for sid in new_ids - returned:
            all_songs[sid] = {"id": sid, "title": f"[unknown_{sid[:8]}]",
                              "_source": "dom_scan_only"}
        print(f"  ✓ Enriched {len(enriched)} songs")

    songs_list = list(all_songs.values())

    # Export
    print("\n📊 Exporting library index...")
    csv_path = output_dir / "suno_library.csv"
    id_path  = output_dir / "song_ids.txt"
    n = export_csv(songs_list, csv_path)
    export_id_list(list(all_songs.keys()), id_path)
    print(f"  ✓ CSV: {csv_path}  ({n} rows)")
    print(f"  ✓ IDs: {id_path}  ({len(all_songs)} entries)")

    return songs_list
