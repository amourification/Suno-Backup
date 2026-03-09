"""
gui.py — Suno Backup GUI  (vibrant cream/orange theme)
=======================================================
Standard-library only (tkinter). No extra deps.

Run:  python gui.py   /   python setup_and_run.py --gui
"""

import json
import os
import platform
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

HERE = Path(__file__).parent.resolve()

# Use config for default output dir (single source of truth)
try:
    from config import OUTPUT_DIR as _DEFAULT_OUTPUT_DIR
except ImportError:
    _DEFAULT_OUTPUT_DIR = HERE / "suno_library"

# ═══════════════════════════════════════════════════════════════════════════════
#  PALETTE  — warm cream base, Suno orange, soft pastels
# ═══════════════════════════════════════════════════════════════════════════════

# backgrounds
CREAM      = "#FDF6EC"   # main window bg — warm off-white
CARD       = "#FFF9F2"   # panel cards
CARD2      = "#FFEFD8"   # slightly deeper card (stats)
SIDEBAR    = "#FFF3E4"   # left column
BORDER     = "#F0D9BB"   # subtle border
BORDER2    = "#E8C99A"   # stronger border / divider

# Suno orange family
ORANGE     = "#FF6B2B"   # primary — Suno signature
ORANGE_LT  = "#FF8C55"   # hover / light variant
ORANGE_DIM = "#C4491A"   # muted orange for labels
ORANGE_PAL = "#FFD4B8"   # pastel orange — badge bg, selected bg

# pastel accent colours
SAGE       = "#7BAF8E"   # success / green
SAGE_PAL   = "#D4EDDA"   # pastel sage bg
ROSE       = "#C96B6B"   # error / stop
ROSE_PAL   = "#FADADD"   # pastel rose bg
SKY        = "#6A9FBF"   # info / scanning
SKY_PAL    = "#D6EAF4"   # pastel sky bg
LAVENDER   = "#9B8EC4"   # accent

# foregrounds
INK        = "#2C1A0E"   # primary text — dark brown
INK2       = "#5C3D1E"   # secondary text
INK3       = "#9A7355"   # tertiary / placeholder
LOG_BG     = "#1E120A"   # log area dark bg
LOG_FG     = "#F0D9BB"   # log text

# ── Fonts ─────────────────────────────────────────────────────────────────────
DISPLAY    = ("Georgia",     20, "bold")
HEAD       = ("Georgia",     13, "bold")
BODY       = ("Georgia",     11)
MONO       = ("Courier New", 10)
MONO_B     = ("Courier New", 11, "bold")
LABEL      = ("Georgia",     10)
SMALL      = ("Georgia",      9)

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════════════════════════════

class SunoBackupApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Suno Backup")
        self.configure(bg=CREAM)
        self.resizable(True, True)
        self.minsize(900, 640)
        self.geometry("1020x740")

        self._proc       = None
        self._log_queue  = queue.Queue()
        self._running    = False
        self._stats      = dict(mp3=0, wav=0, video=0, art=0, total=0, done=0)
        self._anim_tick  = 0
        self._songs_list: list[dict] = []   # from CSV after scan or when loading existing
        self._last_scan_was_scan_only = False

        self._icon_photo = None
        self._icon_photo_small = None
        self._load_icon()

        self._build_ui()
        self._poll_log()
        self._load_config_display()
        self.after(400, self._check_vault_status)
        self.after(600, self._load_songs_into_list)  # fill song list from existing CSV if any

    # ─────────────────────────────────────────────────────────────────────────
    #  ICON
    # ─────────────────────────────────────────────────────────────────────────

    def _load_icon(self):
        """Load app icon from icon.png and set as window icon + keep refs for header."""
        icon_path = HERE / "icon.png"
        if not icon_path.exists():
            return
        try:
            self._icon_photo = tk.PhotoImage(file=str(icon_path))
            self.iconphoto(True, self._icon_photo)
            # Smaller version for header (scale down if large)
            w, h = self._icon_photo.width(), self._icon_photo.height()
            if w > 64 or h > 64:
                self._icon_photo_small = self._icon_photo.subsample(max(1, w // 48), max(1, h // 48))
            else:
                self._icon_photo_small = self._icon_photo
        except Exception:
            self._icon_photo = None
            self._icon_photo_small = None

    # ─────────────────────────────────────────────────────────────────────────
    #  UI CONSTRUCTION
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        _hdivider(self, BORDER2, 2)
        self._build_body()
        _hdivider(self, BORDER2, 1)
        self._build_statusbar()

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = tk.Frame(self, bg=CREAM)
        hdr.pack(fill="x", padx=28, pady=(18, 14))

        # App icon + title
        if self._icon_photo_small:
            tk.Label(hdr, image=self._icon_photo_small, bg=CREAM).pack(side="left")
            tk.Label(hdr, text="  ", bg=CREAM).pack(side="left")
        else:
            logo_pill = tk.Frame(hdr, bg=ORANGE, padx=10, pady=4)
            logo_pill.pack(side="left")
            tk.Label(logo_pill, text="♪", font=("Georgia", 16, "bold"),
                     bg=ORANGE, fg=CREAM).pack(side="left")
            tk.Label(logo_pill, text=" SUNO", font=("Georgia", 14, "bold"),
                     bg=ORANGE, fg=CREAM).pack(side="left")

        tk.Label(hdr, text="Suno Backup", font=DISPLAY,
                 bg=CREAM, fg=INK).pack(side="left", pady=0)
        tk.Label(hdr, text=" — archive your music library",
                 font=BODY, bg=CREAM, fg=INK3).pack(side="left", padx=(4, 0), pady=4)

        # Right side — badge + vault status
        right = tk.Frame(hdr, bg=CREAM)
        right.pack(side="right")

        badge = tk.Label(right, text=" v2.0 ", font=SMALL,
                         bg=ORANGE_PAL, fg=ORANGE_DIM,
                         relief="flat", padx=6, pady=3)
        badge.pack(side="right", padx=(6, 0))

        self._vault_status = tk.Label(right, text="● vault  —",
                                      font=LABEL, bg=CREAM, fg=INK3)
        self._vault_status.pack(side="right")

    # ── Body ──────────────────────────────────────────────────────────────────

    def _build_body(self):
        body = tk.Frame(self, bg=CREAM)
        body.pack(fill="both", expand=True)

        # Sidebar
        sidebar = tk.Frame(body, bg=SIDEBAR, width=298)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        _vdivider(body)
        self._build_sidebar(sidebar)

        # Main panel
        main = tk.Frame(body, bg=CREAM)
        main.pack(side="left", fill="both", expand=True)
        self._build_main(main)

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self, parent):
        wrap = tk.Frame(parent, bg=SIDEBAR, padx=18, pady=16)
        wrap.pack(fill="both", expand=True)

        # OUTPUT DIR
        _sec_label(wrap, "OUTPUT FOLDER")
        out_row = tk.Frame(wrap, bg=SIDEBAR)
        out_row.pack(fill="x", pady=(4, 14))
        self._out_var = tk.StringVar(value=str(_DEFAULT_OUTPUT_DIR))
        e = _entry(out_row, self._out_var, SIDEBAR)
        e.pack(side="left", fill="x", expand=True)
        tk.Button(out_row, text="…", font=LABEL,
                  bg=ORANGE_PAL, fg=ORANGE_DIM,
                  activebackground=ORANGE, activeforeground=CREAM,
                  relief="flat", bd=0, padx=8, pady=4, cursor="hand2",
                  command=self._browse_output).pack(side="right", padx=(5, 0))

        # DOWNLOAD OPTIONS
        _sec_label(wrap, "DOWNLOAD")
        self._mp3_var   = tk.BooleanVar(value=True)
        self._wav_var   = tk.BooleanVar(value=True)
        self._video_var = tk.BooleanVar(value=True)
        self._art_var   = tk.BooleanVar(value=True)
        self._json_var  = tk.BooleanVar(value=True)

        for label, var, badge_txt in [
            ("MP3 audio",     self._mp3_var,   ""),
            ("WAV audio",     self._wav_var,   "PRO"),
            ("WEBM video",    self._video_var, "PRO"),
            ("Cover art",     self._art_var,   ""),
            ("Metadata JSON", self._json_var,  ""),
        ]:
            row = tk.Frame(wrap, bg=SIDEBAR)
            row.pack(fill="x", pady=2)
            _checkbox(row, label, var, SIDEBAR).pack(side="left")
            if badge_txt:
                tk.Label(row, text=f" {badge_txt}", font=SMALL,
                         bg=ORANGE_PAL, fg=ORANGE_DIM,
                         relief="flat", padx=4, pady=1).pack(side="left", padx=(4, 0))

        # RATE LIMITING
        _sec_label(wrap, "WAV DELAY  (seconds)")
        delay_row = tk.Frame(wrap, bg=SIDEBAR)
        delay_row.pack(fill="x", pady=(4, 14))
        self._delay_min = tk.StringVar(value="4")
        self._delay_max = tk.StringVar(value="8")

        tk.Label(delay_row, text="min", font=SMALL, bg=SIDEBAR, fg=INK3).pack(side="left")
        _small_entry(delay_row, self._delay_min, SIDEBAR).pack(side="left", padx=(4, 0))
        tk.Label(delay_row, text="  –  max", font=SMALL, bg=SIDEBAR, fg=INK3).pack(side="left")
        _small_entry(delay_row, self._delay_max, SIDEBAR).pack(side="left", padx=(4, 0))

        # ACTIONS
        _hdivider(wrap, BORDER, 1)
        tk.Frame(wrap, bg=SIDEBAR, height=10).pack()

        self._scan_btn  = _action_btn(wrap, "① Scan Library",  SKY,   SKY_PAL,   self._run_scan)
        self._start_btn = _action_btn(wrap, "② Start Backup",  SAGE,  SAGE_PAL,  self._run_backup)
        self._stop_btn  = _action_btn(wrap, "⏹  Stop",         ROSE,  ROSE_PAL,  self._stop,  state="disabled")
        self._clear_btn = _action_btn(wrap, "✕  Clear Vault",  INK3,  CARD2,     self._clear_vault)

        for b in (self._scan_btn, self._start_btn, self._stop_btn, self._clear_btn):
            b.pack(fill="x", pady=3)

    # ── Main panel ────────────────────────────────────────────────────────────

    def _build_main(self, parent):
        inner = tk.Frame(parent, bg=CREAM, padx=22, pady=16)
        inner.pack(fill="both", expand=True)

        self._build_progress_row(inner)
        self._build_stats_cards(inner)
        self._build_song_list(inner)
        self._build_log(inner)

    def _build_song_list(self, parent):
        """Browsable song list with Select all / Select none for backup selection."""
        frame = tk.Frame(parent, bg=CREAM)
        frame.pack(fill="x", pady=(0, 10))

        row = tk.Frame(frame, bg=CREAM)
        row.pack(fill="x", pady=(0, 4))
        tk.Label(row, text="Songs to download", font=HEAD, bg=CREAM, fg=INK).pack(side="left")
        btn_row = tk.Frame(row, bg=CREAM)
        btn_row.pack(side="right")
        tk.Button(btn_row, text="Select all", font=SMALL,
                  bg=ORANGE_PAL, fg=ORANGE_DIM, relief="flat", bd=0,
                  padx=8, pady=3, cursor="hand2",
                  command=self._select_all_songs).pack(side="left", padx=(0, 4))
        tk.Button(btn_row, text="Select none", font=SMALL,
                  bg=ORANGE_PAL, fg=ORANGE_DIM, relief="flat", bd=0,
                  padx=8, pady=3, cursor="hand2",
                  command=self._select_none_songs).pack(side="left")

        tree_frame = tk.Frame(frame, bg=BORDER2, highlightthickness=1, highlightbackground=BORDER)
        tree_frame.pack(fill="both", expand=False)

        style = ttk.Style(self)
        style.configure("Songs.Treeview", rowheight=22, font=LABEL)
        style.configure("Songs.Treeview.Heading", font=("Georgia", 10, "bold"))
        self._song_tree = ttk.Treeview(
            tree_frame, columns=("title", "id"), show="headings",
            selectmode="extended", height=6, style="Songs.Treeview"
        )
        self._song_tree.heading("title", text="Title")
        self._song_tree.heading("id", text="ID")
        self._song_tree.column("title", width=400, minwidth=200)
        self._song_tree.column("id", width=280, minwidth=100)
        sb = ttk.Scrollbar(tree_frame)
        self._song_tree.configure(yscrollcommand=sb.set)
        sb.configure(command=self._song_tree.yview)
        self._song_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _build_progress_row(self, parent):
        row = tk.Frame(parent, bg=CREAM)
        row.pack(fill="x", pady=(0, 10))

        self._prog_label = tk.Label(row, text="Songs: —", font=LABEL,
                                    bg=CREAM, fg=INK2, anchor="w")
        self._prog_label.pack(side="left")

        self._prog_pct = tk.Label(row, text="", font=("Georgia", 11, "bold"),
                                  bg=CREAM, fg=ORANGE, anchor="e")
        self._prog_pct.pack(side="right")

        # ttk progress bar styled to orange
        s = ttk.Style(self)
        s.theme_use("default")
        s.configure("Suno.Horizontal.TProgressbar",
                    troughcolor=BORDER, background=ORANGE,
                    bordercolor=BORDER, lightcolor=ORANGE_LT, darkcolor=ORANGE_DIM,
                    thickness=8)
        self._prog = ttk.Progressbar(parent, style="Suno.Horizontal.TProgressbar",
                                     mode="determinate", maximum=100)
        self._prog.pack(fill="x", pady=(0, 14))

    def _build_stats_cards(self, parent):
        """Four pastel-tinted stat cards in a row."""
        cards_row = tk.Frame(parent, bg=CREAM)
        cards_row.pack(fill="x", pady=(0, 14))

        self._stat_labels: dict[str, tk.Label] = {}
        defs = [
            ("mp3",   "MP3",  ORANGE_PAL, ORANGE_DIM, "🎵"),
            ("wav",   "WAV",  SKY_PAL,    SKY,        "🎼"),
            ("video", "WEBM", "#D4C8E8", LAVENDER, "🎬"),
            ("art",   "ART",  SAGE_PAL,   SAGE,       "🖼"),
        ]
        for key, label, bg, fg, icon in defs:
            card = tk.Frame(cards_row, bg=bg, padx=0, pady=0,
                            highlightthickness=1, highlightbackground=BORDER)
            card.pack(side="left", expand=True, fill="x", padx=(0, 8))

            inner = tk.Frame(card, bg=bg, padx=14, pady=10)
            inner.pack(fill="both")

            top = tk.Frame(inner, bg=bg)
            top.pack(fill="x")
            tk.Label(top, text=icon + "  " + label, font=SMALL,
                     bg=bg, fg=fg).pack(side="left")

            num = tk.Label(inner, text="—", font=("Georgia", 22, "bold"),
                           bg=bg, fg=INK)
            num.pack(anchor="w", pady=(4, 0))
            self._stat_labels[key] = num

    def _build_log(self, parent):
        # Header row
        hdr = tk.Frame(parent, bg=CREAM)
        hdr.pack(fill="x", pady=(0, 6))

        tk.Label(hdr, text="Activity Log", font=HEAD,
                 bg=CREAM, fg=INK).pack(side="left")

        for label, cmd in [("copy", self._copy_log), ("clear", self._clear_log)]:
            tk.Button(hdr, text=label, font=SMALL,
                      bg=ORANGE_PAL, fg=ORANGE_DIM,
                      activebackground=ORANGE, activeforeground=CREAM,
                      relief="flat", bd=0, padx=8, pady=3, cursor="hand2",
                      command=cmd).pack(side="right", padx=(5, 0))

        # Log text widget — dark bg for terminal feel against the warm UI
        log_outer = tk.Frame(parent, bg=BORDER2, bd=0,
                             highlightthickness=2, highlightbackground=BORDER)
        log_outer.pack(fill="both", expand=True)

        self._log = tk.Text(
            log_outer,
            bg=LOG_BG, fg=LOG_FG,
            font=MONO, wrap="word",
            bd=0, padx=12, pady=10,
            insertbackground=ORANGE,
            selectbackground="#4A2E15",
            selectforeground=CREAM,
            state="disabled",
        )
        sb = tk.Scrollbar(log_outer, bg=LOG_BG, troughcolor=LOG_BG,
                          activebackground="#4A2E15", relief="flat", bd=0,
                          width=10)
        sb.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True)
        self._log["yscrollcommand"] = sb.set
        sb["command"] = self._log.yview

        # Colour tags
        self._log.tag_config("orange",  foreground=ORANGE)
        self._log.tag_config("green",   foreground="#8FCF9E")
        self._log.tag_config("red",     foreground="#E88888")
        self._log.tag_config("sky",     foreground="#88BFDF")
        self._log.tag_config("dim",     foreground="#6B5040")
        self._log.tag_config("bold",    font=MONO_B)
        self._log.tag_config("cream",   foreground=CREAM)

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=CARD2, height=30)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self._status_var = tk.StringVar(value="Ready")
        self._status_pill = tk.Label(bar, bg=ORANGE_PAL, fg=ORANGE_DIM,
                                     width=12, font=SMALL, padx=8)
        self._status_pill.pack(side="left", fill="y", padx=(12, 6))
        self._set_status("ready")

        tk.Label(bar, textvariable=self._status_var, font=LABEL,
                 bg=CARD2, fg=INK2, anchor="w").pack(side="left", fill="y")

        tk.Label(bar, text="Suno Backup v2.0",
                 font=SMALL, bg=CARD2, fg=INK3, padx=12).pack(side="right", fill="y")

    # ─────────────────────────────────────────────────────────────────────────
    #  ACTIONS
    # ─────────────────────────────────────────────────────────────────────────

    def _browse_output(self):
        d = filedialog.askdirectory(initialdir=self._out_var.get())
        if d:
            self._out_var.set(d)

    def _select_all_songs(self):
        if self._song_tree:
            children = self._song_tree.get_children("")
            if children:
                self._song_tree.selection_set(children)

    def _select_none_songs(self):
        if self._song_tree:
            self._song_tree.selection_remove(self._song_tree.get_children(""))

    def _get_csv_path(self) -> Path | None:
        out = Path(self._out_var.get())
        csv_path = out / "suno_library.csv"
        return csv_path if csv_path.exists() else None

    def _load_songs_into_list(self) -> bool:
        """Load songs from OUTPUT/suno_library.csv into _songs_list and tree. Return True if loaded."""
        csv_path = self._get_csv_path()
        if not csv_path:
            return False
        try:
            import csv
            songs = []
            with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sid = (row.get("id") or "").strip()
                    if not sid:
                        continue
                    songs.append(dict(row))
            self._songs_list = songs
            # Populate tree (clear first)
            if self._song_tree:
                for iid in self._song_tree.get_children(""):
                    self._song_tree.delete(iid)
                for s in songs:
                    title = (s.get("title") or s.get("display_name") or s.get("id") or "")[:80]
                    sid = s.get("id") or ""
                    self._song_tree.insert("", "end", iid=sid, values=(title, sid))
            self._select_all_songs()
            return True
        except Exception:
            return False

    def _get_selected_song_ids(self) -> list[str]:
        if not self._song_tree:
            return []
        return list(self._song_tree.selection())

    def _run_scan(self):
        self._last_scan_was_scan_only = True
        self._launch_subprocess(["--scan-only"])

    def _run_backup(self):
        # Use existing scan if we have CSV; otherwise backup will run a full scan
        if not self._songs_list:
            self._load_songs_into_list()
        self._last_scan_was_scan_only = False
        self._launch_subprocess([])

    def _launch_subprocess(self, extra_args: list):
        if self._running:
            return
        self._write_runtime_config()
        python = self._find_python()
        cmd = [python, str(HERE / "suno_backup.py")]

        # If starting backup and we have a previous scan (CSV), use it and pass selected song IDs
        if not extra_args and self._songs_list:  # backup run
            csv_path = self._get_csv_path()
            if csv_path:
                cmd.append("--from-csv")
                cmd.append(str(csv_path.resolve()))
                selected = self._get_selected_song_ids()
                if len(selected) == 0:
                    messagebox.showinfo("No selection", "Select at least one song to download.")
                    return
                if len(selected) < len(self._songs_list):
                    ids_file = HERE / ".gui_selected_ids.txt"
                    ids_file.write_text("\n".join(selected), encoding="utf-8")
                    cmd.append("--song-ids-file")
                    cmd.append(str(ids_file.resolve()))
                # else: all selected → just --from-csv (backup loads all from CSV)
        cmd.extend(extra_args)

        self._running = True
        self._stats   = dict(mp3=0, wav=0, video=0, art=0, total=0, done=0)
        self._update_stats()
        self._prog["value"] = 0
        self._prog_pct.config(text="")
        self._prog_label.config(text="Songs: —")
        self._set_status("running")
        self._scan_btn.config(state="disabled")
        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._log_write(f"\n$ {' '.join(cmd)}\n", "dim")

        def target():
            try:
                self._proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, cwd=str(HERE),
                    env={**os.environ, "PYTHONUNBUFFERED": "1", "SUNO_GUI_MODE": "1"},
                )
                for line in self._proc.stdout:
                    self._log_queue.put(("line", line))
                self._proc.wait()
                self._log_queue.put(("done", self._proc.returncode))
            except Exception as exc:
                self._log_queue.put(("error", str(exc)))

        threading.Thread(target=target, daemon=True).start()

    def _stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self._log_write("\n  ⏹  Stopped by user\n", "red")
        self._finish()

    def _clear_vault(self):
        if messagebox.askyesno("Clear Vault",
                               "Delete the encrypted token vault?\n"
                               "You'll need to log in again on next run."):
            try:
                sys.path.insert(0, str(HERE))
                from vault import clear_vault
                clear_vault()
                self._log_write("  ✓ Vault cleared\n", "green")
                self._check_vault_status()
            except Exception as e:
                self._log_write(f"  ✗ {e}\n", "red")

    # ─────────────────────────────────────────────────────────────────────────
    #  RUNTIME CONFIG SIDECAR
    # ─────────────────────────────────────────────────────────────────────────

    def _write_runtime_config(self):
        cfg = {
            "output_dir":     self._out_var.get(),
            "download_mp3":   self._mp3_var.get(),
            "download_wav":   self._wav_var.get(),
            "download_video": self._video_var.get(),
            "download_art":   self._art_var.get(),
            "download_json":  self._json_var.get(),
            "wav_delay_min":  float(self._delay_min.get() or 4),
            "wav_delay_max":  float(self._delay_max.get() or 8),
        }
        (HERE / ".gui_config.json").write_text(json.dumps(cfg))

    # ─────────────────────────────────────────────────────────────────────────
    #  LOG POLLING
    # ─────────────────────────────────────────────────────────────────────────

    def _poll_log(self):
        try:
            while True:
                kind, data = self._log_queue.get_nowait()
                if kind == "line":
                    self._process_line(data)
                elif kind == "done":
                    if data == 0:
                        self._log_write("\n  ✓ Completed successfully\n", "green")
                        self._set_status("done")
                        self._prog["value"] = 100
                        self._prog_pct.config(text="100%")
                        if getattr(self, "_last_scan_was_scan_only", False):
                            self._load_songs_into_list()
                    else:
                        self._log_write(f"\n  ✗ Exited with code {data}\n", "red")
                        self._set_status("error")
                    self._finish()
                elif kind == "error":
                    self._log_write(f"\n  ✗ {data}\n", "red")
                    self._finish()
        except queue.Empty:
            pass
        self.after(80, self._poll_log)

    def _process_line(self, line: str):
        m_total = re.search(r"Found (\d+) songs",   line)
        if not m_total:
            m_total = re.search(r"(\d+) songs indexed", line)
        if not m_total:
            m_total = re.search(r"(\d+) songs to process", line)
        m_bar   = re.search(r"(\d+)/(\d+)",         line)
        m_mp3   = re.search(r"MP3\s+✓\s+(\d+)",    line)
        m_wav   = re.search(r"WAV\s+✓\s+(\d+)",    line)
        m_video = re.search(r"WEBM\s+✓\s+(\d+)",   line)
        m_art   = re.search(r"Art\s+✓\s+(\d+)",    line)

        if m_total:
            self._stats["total"] = int(m_total.group(1))
        if m_bar and self._stats["total"]:
            self._stats["done"] = int(m_bar.group(1))
            pct = int(self._stats["done"] / self._stats["total"] * 100)
            self._prog["value"] = pct
            self._prog_pct.config(text=f"{pct}%")
            self._prog_label.config(
                text=f"Songs: {self._stats['done']} / {self._stats['total']}")
        for stat, match in [("mp3", m_mp3), ("wav", m_wav),
                             ("video", m_video), ("art", m_art)]:
            if match:
                self._stats[stat] = int(match.group(1))
        self._update_stats()

        # Tag selection
        ll = line.lower()
        if "✓" in line or "complete" in ll:    tag = "green"
        elif "✗" in line or "error" in ll:      tag = "red"
        elif "⚠" in line or "warn" in ll:       tag = "orange"
        elif "→" in line or "download" in ll:   tag = "sky"
        elif line.strip().startswith("♪"):       tag = "bold"
        elif any(c in line for c in ("═","╔","╚")): tag = "orange"
        else:                                    tag = "dim"

        self._log_write(line, tag)

    def _log_write(self, text: str, tag: str = ""):
        self._log.config(state="normal")
        self._log.insert("end", text, tag if tag else ())
        self._log.see("end")
        self._log.config(state="disabled")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    def _copy_log(self):
        self.clipboard_clear()
        self.clipboard_append(self._log.get("1.0", "end"))

    # ─────────────────────────────────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _update_stats(self):
        for key, lbl in self._stat_labels.items():
            v = self._stats.get(key, 0)
            lbl.config(text=str(v) if v else "—",
                       fg=ORANGE if v else INK3)

    def _set_status(self, msg: str):
        self._status_var.set(f"  {msg.capitalize()}")
        colours = {
            "ready":   (ORANGE_PAL,  ORANGE_DIM),
            "running": (SKY_PAL,     SKY),
            "done":    (SAGE_PAL,    SAGE),
            "error":   (ROSE_PAL,    ROSE),
        }
        bg, fg = colours.get(msg.lower(), (ORANGE_PAL, ORANGE_DIM))
        self._status_pill.config(text=f"  {msg.upper()}  ", bg=bg, fg=fg)

    def _finish(self):
        self._running = False
        self._proc    = None
        self._scan_btn.config(state="normal")
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")

    def _check_vault_status(self):
        try:
            sys.path.insert(0, str(HERE))
            from vault import load_tokens, is_token_fresh
            tokens = load_tokens()
            if tokens and is_token_fresh(tokens):
                self._vault_status.config(text="● vault  fresh", fg=SAGE)
            elif tokens:
                self._vault_status.config(text="● vault  stale", fg=ORANGE)
            else:
                self._vault_status.config(text="● vault  empty", fg=INK3)
        except Exception:
            self._vault_status.config(text="● vault  —", fg=INK3)

    def _load_config_display(self):
        try:
            p = HERE / ".gui_config.json"
            if p.exists():
                cfg = json.loads(p.read_text())
                self._out_var.set(cfg.get("output_dir", self._out_var.get()))
                self._mp3_var.set(cfg.get("download_mp3",   True))
                self._wav_var.set(cfg.get("download_wav",   True))
                self._video_var.set(cfg.get("download_video", True))
                self._art_var.set(cfg.get("download_art",   True))
                self._json_var.set(cfg.get("download_json",  True))
                self._delay_min.set(str(cfg.get("wav_delay_min", 4)))
                self._delay_max.set(str(cfg.get("wav_delay_max", 8)))
        except Exception:
            pass

    @staticmethod
    def _find_python() -> str:
        venv_py = HERE / ("venv/Scripts/python.exe"
                          if platform.system() == "Windows"
                          else "venv/bin/python")
        return str(venv_py) if venv_py.exists() else sys.executable


# ═══════════════════════════════════════════════════════════════════════════════
#  WIDGET FACTORY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _hdivider(parent, color=BORDER, h=1):
    tk.Frame(parent, bg=color, height=h).pack(fill="x")

def _vdivider(parent, color=BORDER2, w=1):
    tk.Frame(parent, bg=color, width=w).pack(side="left", fill="y")

def _sec_label(parent, text: str):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(14, 0))
    tk.Label(parent, text=text, font=("Georgia", 9, "bold"),
             bg=parent.cget("bg"), fg=ORANGE_DIM,
             anchor="w", pady=6).pack(fill="x")

def _entry(parent, var, bg_color, width=22):
    return tk.Entry(parent, textvariable=var, width=width,
                    font=LABEL, bg=CARD, fg=INK,
                    insertbackground=ORANGE,
                    relief="flat", bd=0,
                    highlightthickness=1,
                    highlightbackground=BORDER,
                    highlightcolor=ORANGE)

def _small_entry(parent, var, bg_color):
    return tk.Entry(parent, textvariable=var, width=4,
                    font=LABEL, bg=CARD, fg=INK,
                    insertbackground=ORANGE,
                    relief="flat", bd=0,
                    highlightthickness=1,
                    highlightbackground=BORDER,
                    highlightcolor=ORANGE,
                    justify="center")

def _checkbox(parent, label, var, bg_color):
    return tk.Checkbutton(
        parent, text=label, variable=var,
        font=BODY, bg=bg_color, fg=INK,
        activebackground=bg_color, activeforeground=ORANGE,
        selectcolor=CARD,
        highlightthickness=0, bd=0,
    )

def _action_btn(parent, label, fg_color, bg_color, cmd, state="normal"):
    return tk.Button(
        parent, text=label, font=BODY, command=cmd, state=state,
        bg=bg_color, fg=fg_color,
        activebackground=fg_color, activeforeground=CREAM,
        disabledforeground=INK3,
        relief="flat", bd=0,
        padx=12, pady=8,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=fg_color,
        cursor="hand2",
        anchor="w",
    )


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = SunoBackupApp()
    app.mainloop()
