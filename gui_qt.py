"""
gui_qt.py — Suno Backup Qt GUI (PySide6).
Application entry and business logic; UI is in ui/main_window.py.
Run:  python gui_qt.py   /   python setup_and_run.py --gui
"""

import csv
import json
import os
import platform
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer

HERE = Path(__file__).parent.resolve()

try:
    from config import OUTPUT_DIR as _DEFAULT_OUTPUT_DIR, resolve_output_dir, output_dir_to_config_value
except ImportError:
    _DEFAULT_OUTPUT_DIR = Path.home() / "Downloads" / "Suno Backup"
    def resolve_output_dir(candidate, base):
        return _DEFAULT_OUTPUT_DIR.resolve()
    def output_dir_to_config_value(path, base):
        return str(_DEFAULT_OUTPUT_DIR)

from ui.main_window import MainWindow
from ui.theme import SUCCESS, WARNING, TEXT_TERTIARY, LOG_SUCCESS, LOG_ERROR, LOG_WARN, LOG_DIM, INFO, LOG_FG


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _find_python() -> str:
    venv_py = HERE / (
        "venv/Scripts/python.exe" if platform.system() == "Windows" else "venv/bin/python"
    )
    return str(venv_py) if venv_py.exists() else sys.executable


class SunoBackupController:
    """Wires MainWindow to backup/scan subprocess, config, vault, and log polling."""

    def __init__(self):
        self._proc = None
        self._log_queue = queue.Queue()
        self._running = False
        self._last_scan_was_scan_only = False
        self._stats = dict(mp3=0, wav=0, video=0, art=0, total=0, done=0,
                           mp3_fail=0, wav_fail=0, video_fail=0)
        self._current_song_title = None
        self._songs_list: list[dict] = []

        default_out = str(_DEFAULT_OUTPUT_DIR)
        icon_path = HERE / "icon.png"
        self._win = MainWindow(default_output_dir=default_out, icon_path=icon_path)

        self._connect_ui()
        self._load_config_display()
        QTimer.singleShot(400, self._check_vault_status)
        QTimer.singleShot(600, self._load_songs_into_list)
        self._poll_timer = QTimer(self._win)
        self._poll_timer.timeout.connect(self._poll_log)
        self._poll_timer.start(80)

    def _connect_ui(self):
        self._win.scan_btn.clicked.connect(self._run_scan)
        self._win.start_btn.clicked.connect(self._run_backup)
        self._win.stop_btn.clicked.connect(self._stop)
        self._win.clear_vault_btn.clicked.connect(self._clear_vault)
        self._win.select_all_btn.clicked.connect(self._win.select_all_songs)
        self._win.select_none_btn.clicked.connect(self._win.select_none_songs)
        self._win.copy_log_btn.clicked.connect(self._copy_log)
        self._win.clear_log_btn.clicked.connect(self._win.log_clear)
        # show_log_btn removed from MainWindow; do not re-add

    def _get_csv_path(self) -> Path | None:
        out = Path(self._win.get_output_dir())
        csv_path = out / "suno_library.csv"
        return csv_path if csv_path.exists() else None

    def _load_songs_into_list(self) -> bool:
        csv_path = self._get_csv_path()
        if not csv_path:
            return False
        try:
            self._songs_list = []
            with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    sid = (row.get("id") or "").strip()
                    if not sid:
                        continue
                    self._songs_list.append(dict(row))
            self._win.song_tree_clear()
            for s in self._songs_list:
                title = (s.get("title") or s.get("display_name") or s.get("id") or "")[:80]
                sid = s.get("id") or ""
                self._win.song_tree_add(sid, title)
            self._win.select_all_songs()
            return True
        except Exception:
            return False

    def _run_scan(self):
        self._last_scan_was_scan_only = True
        self._launch_subprocess(["--scan-only"])

    def _run_backup(self):
        if not self._songs_list:
            self._load_songs_into_list()
        self._last_scan_was_scan_only = False
        self._launch_subprocess([])

    def _launch_subprocess(self, extra_args: list):
        if self._running:
            return
        self._write_runtime_config()
        python = _find_python()
        cmd = [python, str(HERE / "suno_backup.py")]

        if not extra_args and self._songs_list:
            csv_path = self._get_csv_path()
            if csv_path:
                cmd.append("--from-csv")
                cmd.append(str(csv_path.resolve()))
                selected = self._win.get_selected_song_ids()
                if len(selected) == 0:
                    QMessageBox.information(
                        self._win,
                        "No selection",
                        "Select at least one song to download.",
                    )
                    return
                if len(selected) < len(self._songs_list):
                    ids_file = HERE / ".gui_selected_ids.txt"
                    ids_file.write_text("\n".join(selected), encoding="utf-8")
                    cmd.append("--song-ids-file")
                    cmd.append(str(ids_file.resolve()))
        cmd.extend(extra_args)

        self._running = True
        self._stats = dict(mp3=0, wav=0, video=0, art=0, total=0, done=0,
                           mp3_fail=0, wav_fail=0, video_fail=0)
        self._current_song_title = None
        self._update_stats()
        self._win.set_progress(0, 0, 0)
        self._win.set_current_track(None)
        self._win.set_phase_step(-1)
        self._win.set_status("Running")
        self._win.set_running(True)
        self._log_write(f"\n$ {' '.join(cmd)}\n", "dim")

        def target():
            proc = None
            returncode = None
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    cwd=str(HERE),
                    env={**os.environ, "PYTHONUNBUFFERED": "1", "SUNO_GUI_MODE": "1"},
                )
                self._proc = proc
                for line in proc.stdout:
                    self._log_queue.put(("line", line))
                returncode = proc.wait(timeout=30)
                self._log_queue.put(("done", returncode))
            except subprocess.TimeoutExpired:
                if proc:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                self._log_queue.put(("error", "Process did not exit"))
                self._log_queue.put(("done", -1))
            except Exception as exc:
                self._log_queue.put(("error", str(exc)))
                self._log_queue.put(("done", returncode if returncode is not None else -1))
            finally:
                self._proc = None

        threading.Thread(target=target, daemon=True).start()

    def _stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self._log_write("\n  ⏹  Stopped by user\n", "red")
        self._finish()

    def _clear_vault(self):
        if (
            QMessageBox.Yes
            == QMessageBox.question(
                self._win,
                "Clear Vault",
                "Delete the encrypted token vault?\nYou'll need to log in again on next run.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
        ):
            try:
                sys.path.insert(0, str(HERE))
                from vault import clear_vault

                clear_vault()
                self._log_write("  ✓ Vault cleared\n", "green")
                self._check_vault_status()
            except Exception as e:
                self._log_write(f"  ✗ {e}\n", "red")

    def _write_runtime_config(self):
        flags = self._win.get_download_flags()
        mn, mx = self._win.get_wav_delay()
        out_dir_raw = (self._win.get_output_dir() or "").strip()
        resolved = resolve_output_dir(out_dir_raw if out_dir_raw else None, HERE)
        cfg = {
            "output_dir": output_dir_to_config_value(resolved, HERE),
            "download_mp3": flags["download_mp3"],
            "download_wav": flags["download_wav"],
            "download_video": flags["download_video"],
            "download_art": flags["download_art"],
            "download_json": flags["download_json"],
            "wav_delay_min": mn,
            "wav_delay_max": mx,
        }
        (HERE / ".gui_config.json").write_text(json.dumps(cfg))

    def _poll_log(self):
        try:
            while True:
                kind, data = self._log_queue.get_nowait()
                if kind == "line":
                    self._process_line(data)
                elif kind == "done":
                    if data == 0:
                        self._log_write("\n  ✓ Completed successfully\n", "green")
                        self._win.set_status("Done")
                        self._win.set_progress(
                            self._stats.get("total", 0),
                            self._stats.get("total", 0),
                            100,
                        )
                        if self._last_scan_was_scan_only:
                            self._load_songs_into_list()
                    else:
                        self._log_write(f"\n  ✗ Exited with code {data}\n", "red")
                        self._win.set_status("Error")
                    self._finish()
                elif kind == "error":
                    self._log_write(f"\n  ✗ {data}\n", "red")
                    self._finish()
        except queue.Empty:
            pass

    def _process_line(self, line: str):
        m_total = re.search(r"Found (\d+) songs", line)
        if not m_total:
            m_total = re.search(r"(\d+) songs indexed", line)
        if not m_total:
            m_total = re.search(r"(\d+) songs to process", line)
        m_bar = re.search(r"(\d+)/(\d+)", line)
        m_mp3 = re.search(r"MP3\s+✓\s+(\d+)", line)
        m_wav = re.search(r"WAV\s+✓\s+(\d+)", line)
        m_video = re.search(r"(?:Video|WEBM)\s+✓\s+(\d+)", line)
        m_art = re.search(r"Art\s+✓\s+(\d+)", line)
        m_mp3_fail = re.search(r"MP3\s+✓\s+\d+\s+✗\s+(\d+)", line)
        m_wav_fail = re.search(r"WAV\s+✓\s+\d+\s+✗\s+(\d+)", line)
        m_video_fail = re.search(r"Video\s+✓\s+\d+\s+✗\s+(\d+)", line)

        if m_total:
            self._stats["total"] = int(m_total.group(1))
        if m_bar and self._stats.get("total"):
            self._stats["done"] = int(m_bar.group(1))
            pct = int(self._stats["done"] / self._stats["total"] * 100)
            self._win.set_progress(
                self._stats["done"], self._stats["total"], pct
            )
        for stat, match in [
            ("mp3", m_mp3),
            ("wav", m_wav),
            ("video", m_video),
            ("art", m_art),
        ]:
            if match:
                self._stats[stat] = int(match.group(1))
        for stat, match in [("mp3_fail", m_mp3_fail), ("wav_fail", m_wav_fail), ("video_fail", m_video_fail)]:
            if match:
                self._stats[stat] = int(match.group(1))
        self._update_stats()

        line_stripped = line.strip()
        if "→ Cover art" in line or "→ Cover" in line_stripped:
            self._win.set_phase_step(1)
        elif "→ MP3" in line:
            self._win.set_phase_step(2)
        elif "→ Video" in line or "→ Video (MP4)" in line:
            self._win.set_phase_step(3)
        elif "→ WAV" in line:
            self._win.set_phase_step(4)
        elif "→ Embedded" in line or "Embedded cover" in line:
            self._win.set_phase_step(5)
        elif line_stripped.startswith("♪"):
            m_song = re.search(r"♪\s+(.+?)\s+\[", line)
            if m_song:
                self._current_song_title = m_song.group(1).strip()
                self._win.set_current_track(self._current_song_title)
                self._win.set_phase_step(0)
                self._win.add_activity_event(f"Processing: {self._current_song_title[:50]}", "info")

        ll = line.lower()
        if "✓" in line or "complete" in ll:
            tag = "green"
        elif "✗" in line or "error" in ll:
            tag = "red"
        elif "⚠" in line or "warn" in ll:
            tag = "orange"
        elif "→" in line or "download" in ll:
            tag = "sky"
        elif line_stripped.startswith("♪"):
            tag = "bold"
        elif any(c in line for c in ("═", "╔", "╚")):
            tag = "orange"
        else:
            tag = "dim"

        if not re.search(r"Downloading:\s*\d+%\|", line) and not (
            re.search(r"\d+/\d+\s+\[\d+:\d+<", line) and "song" in ll
        ):
            if "✓ WAV downloaded" in line or "✓ WAV downloaded (from API" in line:
                title = (self._current_song_title or "Track")[:40]
                self._win.add_activity_event(f"{title} — WAV ✓", "success")
            elif "✓" in line and "MP3" in line and "download" in ll:
                title = (self._current_song_title or "Track")[:40]
                self._win.add_activity_event(f"{title} — MP3 ✓", "success")
            elif "✓" in line and "Video" in line:
                title = (self._current_song_title or "Track")[:40]
                self._win.add_activity_event(f"{title} — Video ✓", "success")
            elif "✓" in line and "Cover" in line:
                title = (self._current_song_title or "Track")[:40]
                self._win.add_activity_event(f"{title} — Cover ✓", "success")
            elif "✗ HTTP 403" in line or "✗ HTTP" in line:
                title = (self._current_song_title or "Track")[:40]
                self._win.add_activity_event(f"{title} — Failed", "error")
            elif "Completed successfully" in line:
                self._win.add_activity_event("Backup complete", "success")
            elif "✓" in line and "songs indexed" in ll and m_total:
                self._win.add_activity_event(f"Scan complete: {m_total.group(1)} songs", "success")

        if re.search(r"Downloading:\s*\d+%\|", line) or (
            re.search(r"\d+/\d+\s+\[\d+:\d+<", line) and "song" in ll and line_stripped.startswith("Downloading")
        ):
            return
        self._log_write(line.rstrip(), tag)

    _LOG_TAG_COLORS = {
        "green": LOG_SUCCESS,
        "red": LOG_ERROR,
        "orange": LOG_WARN,
        "sky": INFO,
        "dim": LOG_DIM,
        "bold": LOG_FG,
    }

    def _log_write(self, text: str, tag: str = ""):
        color = self._LOG_TAG_COLORS.get(tag) if tag else None
        escaped = _html_escape(text.rstrip())
        self._win.log_append(escaped, color)

    def _copy_log(self):
        app = QApplication.instance()
        if app:
            app.clipboard().setText(self._win.log_plain_text())

    def _update_stats(self):
        total = self._stats.get("total") or 0
        for key in ("mp3", "wav", "video", "art"):
            v = self._stats.get(key, 0)
            self._win.set_stat(key, str(v) if v else "0")
            if total:
                pct = int(v / total * 100)
                self._win.set_format_progress(key, pct)
        for key, fkey in [("mp3_fail", "mp3"), ("wav_fail", "wav"), ("video_fail", "video")]:
            self._win.set_stat_fail(fkey, self._stats.get(key, 0))

    def _finish(self):
        self._running = False
        self._proc = None
        self._win.set_running(False)
        self._win.set_current_track(None)
        self._win.set_phase_step(-1)

    def _check_vault_status(self):
        try:
            sys.path.insert(0, str(HERE))
            from vault import load_tokens, is_token_fresh

            tokens = load_tokens()
            if tokens and is_token_fresh(tokens):
                self._win.set_vault_status("Vault — fresh", SUCCESS)
            elif tokens:
                self._win.set_vault_status("Vault — stale", WARNING)
            else:
                self._win.set_vault_status("Vault — empty", TEXT_TERTIARY)
        except Exception:
            self._win.set_vault_status("Vault — —", TEXT_TERTIARY)

    def _load_config_display(self):
        try:
            p = HERE / ".gui_config.json"
            safe_dir = resolve_output_dir(None, HERE)
            output_dir_to_use = str(safe_dir)
            if p.exists():
                cfg = json.loads(p.read_text())
                saved_out = (cfg.get("output_dir") or "").strip()
                resolved = resolve_output_dir(saved_out if saved_out else None, HERE)
                output_dir_to_use = str(resolved)
                self._win.set_output_dir(output_dir_to_use)
                self._win.set_download_flags(
                    {
                        "download_mp3": cfg.get("download_mp3", True),
                        "download_wav": cfg.get("download_wav", True),
                        "download_video": cfg.get("download_video", True),
                        "download_art": cfg.get("download_art", True),
                        "download_json": cfg.get("download_json", True),
                    }
                )
                self._win.set_wav_delay(
                    float(cfg.get("wav_delay_min", 4)),
                    float(cfg.get("wav_delay_max", 8)),
                )
                cfg["output_dir"] = output_dir_to_config_value(resolved, HERE)
                p.write_text(json.dumps(cfg))
            else:
                self._win.set_output_dir(output_dir_to_use)
        except Exception:
            pass

    def show(self):
        self._win.show()


def main():
    app = QApplication(sys.argv)
    icon_path = HERE / "icon.png"
    if icon_path.exists():
        try:
            from PySide6.QtGui import QIcon

            app.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass
    ctrl = SunoBackupController()
    ctrl.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
