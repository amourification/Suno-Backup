<div align="center">

<br/>

```
♪  S U N O   B A C K U P
```

### **Never lose a song again.**

Your Suno library, downloaded locally. Every format. Every track. One click.

<br/>

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-FF6B2B?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-FDF6EC?style=flat-square)](#quick-start)
[![License](https://img.shields.io/badge/License-MIT-FF8C55?style=flat-square)](#)
[![Suno Pro](https://img.shields.io/badge/Suno-Pro%20%E2%9C%93-FF6B2B?style=flat-square)](https://suno.com)


[![Buy Me A Coffee](https://img.shields.io/badge/Buy_Me_A_Coffee-FFDD00?style=flat-square&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/amourification)


<a href="https://www.producthunt.com/products/suno-backup/reviews/new?utm_source=badge-product_review&utm_medium=badge&utm_source=badge-suno&#0045;backup" target="_blank"><img src="https://api.producthunt.com/widgets/embed-image/v1/product_review.svg?product_id=1177559&theme=light" alt="Suno&#0032;Backup - One&#0045;click&#0032;backup&#0032;for&#0032;your&#0032;entire&#0032;Suno&#0032;music&#0032;library&#0046; | Product Hunt" style="width: 250px; height: 54px;" width="250" height="54" /></a>

<br/>

</div>

---

## ✨ The Ultimate Suno Archiver

**The only tool on the internet** that does it all in one click:
🔥 Triggers and downloads native **WAV masters** (Pro)
🎨 Creates high-quality **MP3s with embedded cover art**
🗂️ Organizes everything into a **perfect folder structure** with a complete CSV library logbook.

## ✨ Why This Exists

You've spent hours — maybe *hundreds* of hours — creating music on Suno. Prompts perfected, styles refined, hidden gems buried three pages deep in your library.

**Suno doesn't have a bulk export button.** You do now.

Suno Backup scans your entire library using Suno's own private API, extracts every song ID it can find, and downloads everything to your local machine — organized, labeled, and ready for any DAW, streaming service, or personal archive.

<br/>

## 🎵 What Gets Downloaded

| Format | Details |
|--------|---------|
| 🎵 **MP3** | Full-quality stream audio |
| 🎼 **WAV** | Lossless master — triggers Suno's server-side conversion automatically *(Pro)* |
| 🎬 **WEBM** | Music video with visualizer *(Pro)* |
| 🖼️ **Cover Art** | High-res JPEG thumbnail |
| 📄 **Metadata JSON** | Full API response — prompts, tags, model, stats |
| 📊 **CSV Index** | Your entire library in a spreadsheet, with every CDN URL pre-computed |

<br/>

## 🚀 Quick Start

> **No terminal experience needed.** Just double-click and log in.

There are **two launchers per OS**: one for the **terminal (CLI)** backup flow, one for the **desktop GUI**. Use whichever you prefer.

| You want… | Windows | macOS / Linux |
|-----------|--------|----------------|
| **Terminal** — run in a console, type Y to download | `START_WINDOWS.bat` | `bash START_MAC_LINUX.sh` |
| **GUI** — window with Scan / Backup buttons | `START_GUI_WINDOWS.bat` | `bash START_GUI_MAC_LINUX.sh` |

### Windows
```
Double-click  →  START_WINDOWS.bat        (CLI)
             →  START_GUI_WINDOWS.bat     (GUI)
```

### macOS / Linux
```bash
bash START_MAC_LINUX.sh        # CLI
bash START_GUI_MAC_LINUX.sh    # GUI
```

That's genuinely it. On first run, the tool will:

1. 📦 Create a self-contained Python virtual environment
2. 📥 Install all dependencies automatically
3. 🌐 Install a Playwright Chromium browser
4. 🔐 Open a browser window — **log in to Suno as normal**
5. 🔍 Scan your entire library (three-phase: API + DOM + batch enrichment)
6. 📊 Export a full CSV index of every song
7. ⬇️ Download everything, skipping files already on disk

<br/>

## 📦 Creating Standalone Executables

If you'd rather run the app without touching Python files or launchers at all, you can build a native `.exe` or executable for your platform. 

Simply run the included build scripts (ensure you have Python installed first):

- **Windows:** Run `build_windows.bat`
- **macOS / Linux:** Run `bash build_mac_linux.sh`

This uses `PyInstaller` to bundle the app. Once finished, check the `dist/` folder for your standalone `Suno Backup` application!

<br/>

## 🖥️ GUI Preview

```
┌─────────────────────────────────────────────────────────────┐
│  ♪ SUNO  BACKUP  — archive your music library    v2.0  ●    │
├──────────────────────┬──────────────────────────────────────┤
│  OUTPUT FOLDER       │  Songs: 312 / 847            64%     │
│  ~/suno_library  […] │  ████████████████░░░░░░░░░░░░        │
│                      │                                       │
│  DOWNLOAD            │  🎵 MP3   🎼 WAV   🎬 WEBM   🖼 ART  │
│  ✓ MP3 audio         │   312     298      241        312     │
│  ✓ WAV audio   PRO   │                                       │
│  ✓ WEBM video  PRO   │  Activity Log                         │
│  ✓ Cover art         │  ┌───────────────────────────────┐   │
│  ✓ Metadata JSON     │  │ ♪ Midnight Frequency           │   │
│                      │  │   → WAV (convert + download)  │   │
│  WAV DELAY           │  │   ✓ Cover art (JPEG)          │   │
│  min 4  –  max 8     │  │   → MP3...                    │   │
│                      │  └───────────────────────────────┘   │
│  ① Scan Library      │                                       │
│  ② Start Backup      │                                       │
│  ⏹  Stop             │                                       │
│  ✕  Clear Vault      │                                       │
├──────────────────────┴──────────────────────────────────────┤
│  RUNNING    Downloading song 312 of 847              v2.0   │
└─────────────────────────────────────────────────────────────┘
```

<br/>

## 🗂️ Output Structure

Your library lands organized and clean:

```
suno_library/
├── suno_library.csv          ← your full library in a spreadsheet
├── song_ids.txt              ← plain list of every discovered ID
│
├── Midnight_Frequency__43b0804d/
│   ├── metadata.json         ← prompt, tags, model, stats
│   ├── image_43b0804d.jpeg   ← cover art
│   ├── Midnight_Frequency.mp3
│   ├── Midnight_Frequency.wav
│   └── Midnight_Frequency.webm
│
├── Desert_Radio__8f2a1c9e/
│   └── ...
```

Every song gets its own folder named `Title__UUID` — human-readable and collision-proof.

<br/>

## 🔍 How the Library Scanner Works

Most tools stop at the public API. This one doesn't.

**Phase 1 — API feed pagination**
Walks through `/api/feed/v2/` page by page until the list is exhausted. Gets everything Suno officially exposes.

**Phase 2 — DOM scraping**
Opens your library in a headless browser and scans the raw HTML for UUID patterns: `image_{id}.jpeg`, `{id}.webm`, `{id}.mp3`, `/song/{id}` hrefs, and embedded JSON blobs. Catches songs the API misses.

**Phase 3 — Batch enrichment**
Any IDs found only in the DOM — not in the API feed — get sent to `/api/get_songs_by_ids` in batches of 20 to pull their full metadata.

The result: a CSV with **every song you've ever created**, including ones buried beyond the API's default pagination.

<br/>

## 🔒 Security

Your login tokens never leave your machine.

Tokens are encrypted with **Fernet (AES-128-CBC + HMAC-SHA256)** and stored in a hidden `.suno_vault` file. The encryption key is derived from your machine's unique hardware fingerprint — hostname, MAC address, machine GUID, and a locally-generated random salt. The vault file is **unreadable on any other machine**, even if someone copies it.

Tokens auto-refresh before expiry so long backups don't suddenly fail mid-run.

```
your login  →  browser session  →  token captured  →  AES encrypted  →  .suno_vault
                                                          ↑
                                              machine fingerprint + random salt
```

<br/>

## ⚙️ Configuration

Everything can be set via the GUI, or edited directly in `config.py`:

```python
# Toggle what gets downloaded
DOWNLOAD_MP3   = True
DOWNLOAD_WAV   = True     # Pro subscribers
DOWNLOAD_VIDEO = True     # Pro subscribers
DOWNLOAD_ART   = True
DOWNLOAD_JSON  = True

# Human-like request timing (randomised to avoid bot detection)
RATE_LIMIT_WAV_MIN  = 4.0   # seconds between WAV conversions
RATE_LIMIT_WAV_MAX  = 8.0
RATE_LIMIT_PAGE_MIN = 1.5   # seconds between feed pages
RATE_LIMIT_PAGE_MAX = 3.5
```

<br/>

## 🧪 Running the Tests

```bash
# from the project root (inside venv)
python -m pytest tests/ -v
```

Covers: `sanitize()`, `_flatten_song()`, `_extract_ids_from_html()`, vault encryption/decryption, CSV export, and ID deduplication.

<br/>

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| Python not found | Install [Python 3.9+](https://python.org) — check *"Add to PATH"* on Windows |
| Login window doesn't appear | Run `python setup_and_run.py` directly from a terminal |
| WAV fails for specific songs | Some songs aren't WAV-eligible; the tool logs it and continues |
| Auth error mid-backup | Re-run — already-downloaded files are automatically skipped |
| Vault decryption error | Delete `.suno_vault` and `.vault_salt`, then re-run to re-authenticate |
| CSV is empty | Confirm you're logged into the correct Suno account |
| Rate limited | Increase `RATE_LIMIT_*_MIN/MAX` values in `config.py` |
| GUI doesn't open / window closes right away | If the GUI fails to start, the launcher will keep the window open so you can read the error. Run `python setup_and_run.py --gui` from a terminal to see the full traceback. |

<br/>

## 📁 Project Layout

```
suno_backup_v2/
├── setup_and_run.py       one-click launcher & venv bootstrapper
├── suno_backup.py         download orchestrator
├── scanner.py             3-phase library scanner + CSV exporter
├── vault.py               AES-encrypted token storage
├── config.py              all constants — single source of truth
├── gui.py                 desktop GUI (tkinter, no extra deps)
├── requirements.txt
│
├── tests/
│   └── test_core.py       unit tests (pytest)
│
├── START_WINDOWS.bat           → CLI mode, Windows
├── START_MAC_LINUX.sh          → CLI mode, macOS/Linux
├── START_GUI_WINDOWS.bat       → GUI mode, Windows
└── START_GUI_MAC_LINUX.sh      → GUI mode, macOS/Linux
```

<br/>

## 📋 Requirements

Auto-installed on first run. Nothing to do manually.

```
playwright >= 1.40    browser automation & token capture
requests   >= 2.31    HTTP downloads
tqdm       >= 4.66    progress bars
cryptography >= 41.0  vault encryption
```

<br/>

---

<div align="center">

**Enjoying the tool?**  
<a href="https://buymeacoffee.com/amourification" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 40px !important;width: 145px !important;" ></a>

<br/>
<br/>

Made for Suno creators who want to own their music. 🎶

*This software is an independent, third-party tool and is not affiliated with, endorsed by, or sponsored by Suno, Inc. "Suno" and all related names, logos, and content are the trademarks and exclusive property of Suno, Inc. Users of this tool are solely responsible for ensuring their use complies with [Suno's Terms of Service](https://suno.com/terms).*

</div>
