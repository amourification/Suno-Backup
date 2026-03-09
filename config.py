"""
config.py — Single source of truth for all constants and settings
=================================================================
All other modules import from here. Never define API_BASE, CDN_BASE,
SESSION_DIR, or OUTPUT_DIR in more than one place.
"""

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
HERE        = Path(__file__).parent.resolve()
OUTPUT_SUBDIR = "Suno Backup"
OUTPUT_DIR  = Path.home() / "Downloads" / OUTPUT_SUBDIR
SESSION_DIR = HERE / "suno_session"
VAULT_FILE  = HERE / ".suno_vault"
SALT_FILE   = HERE / ".vault_salt"


def resolve_output_dir(candidate: str | None, base: Path) -> Path:
    """
    Resolve output directory.
    - None or empty -> OUTPUT_DIR
    - Relative path -> relative to base (app folder)
    - Absolute path -> raw absolute path
    """
    if not (candidate and str(candidate).strip()):
        return OUTPUT_DIR
    raw = Path(candidate.strip())
    try:
        if not raw.is_absolute():
            return (base / raw).resolve()
        return raw.resolve()
    except (ValueError, OSError):
        return OUTPUT_DIR


def output_dir_to_config_value(path: Path, base: Path) -> str:
    """
    Serialize output path for .gui_config.json.
    """
    try:
        return str(path.resolve()).replace("\\", "/")
    except Exception:
        return str(OUTPUT_DIR).replace("\\", "/")

# ── API endpoints ─────────────────────────────────────────────────────────────
API_BASE    = "https://studio-api.prod.suno.com"
CDN_BASE    = "https://cdn1.suno.ai"
SUNO_ME     = "https://suno.com/me"

# ── Pagination & batching ─────────────────────────────────────────────────────
PAGE_SIZE   = 20     # songs per /api/feed/v2/ page
BATCH_SIZE  = 20     # IDs per /api/get_songs_by_ids call

# ── Download flags (can be overridden at runtime) ─────────────────────────────
DOWNLOAD_MP3   = True
DOWNLOAD_WAV   = True     # Pro subscribers only
DOWNLOAD_VIDEO = False   # .mp4 from CDN — often 403; set True only if you need video
DOWNLOAD_ART   = True     # image_{id}.jpeg
DOWNLOAD_JSON  = True     # raw API metadata

# ── Naming ───────────────────────────────────────────────────────────────────
# Folder name: {title}__{short_id}. Use 0 for full UUID (long names).
SHORT_ID_LEN   = 8       # first N chars of UUID (no dashes) in folder name

# ── Post-download ───────────────────────────────────────────────────────────
# Embed cover image into audio files (MP3: ID3 APIC; WAV: ID3 if supported).
EMBED_COVER_ART = True

# ── Timing & rate limiting ────────────────────────────────────────────────────
# All delays are in seconds. Ranges produce uniform random jitter
# to appear human and avoid bot-detection heuristics.

RATE_LIMIT_WAV_MIN   = 4.0    # min delay between WAV convert calls
RATE_LIMIT_WAV_MAX   = 8.0    # max delay — randomised each time

RATE_LIMIT_DL_MIN    = 1.0    # min delay between generic file downloads
RATE_LIMIT_DL_MAX    = 3.0    # max delay

RATE_LIMIT_PAGE_MIN  = 1.5    # min delay between feed page fetches
RATE_LIMIT_PAGE_MAX  = 3.5    # max delay

RATE_LIMIT_BATCH_MIN = 0.8    # min delay between get_songs_by_ids batches
RATE_LIMIT_BATCH_MAX = 2.0    # max delay

WAV_POLL_RETRIES     = 14
WAV_POLL_WAIT_MIN    = 4.0
WAV_POLL_WAIT_MAX    = 7.0

# ── Token freshness ───────────────────────────────────────────────────────────
TOKEN_MAX_AGE_SEC    = 3000   # refresh tokens after ~50 min (expire at 60)

# ── Browser ───────────────────────────────────────────────────────────────────
BROWSER_VIEWPORT     = {"width": 1280, "height": 860}
LOGIN_TIMEOUT_MS     = 180_000   # 3 min to complete login

# ── CSV column order ──────────────────────────────────────────────────────────
# Status columns are updated after each song during backup (has_* = 1 when file exists).
CSV_FIELDS = [
    "id", "title", "display_name", "status", "duration", "created_at",
    "audio_url", "wav_url", "video_url", "image_url", "image_large_url",
    "model_name", "tags", "prompt", "style",
    "is_public", "play_count", "upvote_count", "source",
    "has_mp3", "has_wav", "has_video", "has_metadata", "has_cover",
    "last_updated_utc",
]
