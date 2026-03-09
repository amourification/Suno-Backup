#!/usr/bin/env python3
"""
setup_and_run.py — One-click setup & launcher (OS-agnostic)
============================================================
Double-click or: python setup_and_run.py
  1. Creates ./venv/
  2. Installs requirements.txt
  3. Installs Playwright Chromium
  4. Launches suno_backup.py inside the venv
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

HERE        = Path(__file__).parent.resolve()
VENV_DIR    = HERE / "venv"
MAIN_SCRIPT = HERE / "suno_backup.py"
REQ_FILE    = HERE / "requirements.txt"
IS_WINDOWS  = platform.system() == "Windows"


def venv_python() -> Path:
    if IS_WINDOWS:
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(cmd: list, **kw):
    print(f"\n  $ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        print(f"\n  ERROR: exit code {r.returncode}")
        sys.exit(r.returncode)


def check_python():
    major, minor = sys.version_info[:2]
    print(f"  Python {major}.{minor}  ({sys.executable})")
    if (major, minor) < (3, 9):
        print("  ERROR: Python 3.9+ required.")
        sys.exit(1)


def create_venv():
    if venv_python().exists():
        print("  ✓ venv exists — skipping")
        return
    print("  Creating virtual environment...")
    run([sys.executable, "-m", "venv", str(VENV_DIR)])


def install_requirements():
    if not REQ_FILE.exists():
        print("  ERROR: requirements.txt not found.")
        sys.exit(1)
    print("  Installing packages...")
    run([str(venv_python()), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    run([str(venv_python()), "-m", "pip", "install", "--quiet", "-r", str(REQ_FILE)])


def install_playwright():
    marker = VENV_DIR / ".playwright_installed"
    if marker.exists():
        print("  ✓ Playwright Chromium installed — skipping")
        return
    print("  Installing Playwright Chromium...")
    run([str(venv_python()), "-m", "playwright", "install", "chromium"])
    marker.touch()


def launch():
    if not MAIN_SCRIPT.exists():
        print(f"  ERROR: {MAIN_SCRIPT} not found.")
        sys.exit(1)
    print("\n" + "=" * 56)
    print("  Launching Suno Backup Tool...")
    print("=" * 56 + "\n")
    if IS_WINDOWS:
        # On Windows, os.execv() mangles paths with spaces (e.g. "Suno Backup App").
        # Use subprocess so the argument list is passed correctly to CreateProcess.
        proc = subprocess.Popen(
            [str(venv_python()), str(MAIN_SCRIPT)] + sys.argv[1:],
            cwd=str(HERE),
        )
        sys.exit(proc.wait())
    os.execv(str(venv_python()), [str(venv_python()), str(MAIN_SCRIPT)] + sys.argv[1:])


def launch_gui():
    gui_script = HERE / "gui_qt.py"
    if not gui_script.exists():
        gui_script = HERE / "gui.py"
    if not (HERE / "suno_backup.py").exists():
        print(f"  ERROR: suno_backup.py not found.")
        sys.exit(1)
    if not gui_script.exists():
        print("  ERROR: gui_qt.py / gui.py not found.")
        sys.exit(1)
    print("\n" + "=" * 56)
    print("  Launching Suno Backup GUI...")
    print("=" * 56 + "\n")
    if IS_WINDOWS:
        # On Windows, os.execv() mangles paths with spaces; use subprocess instead.
        proc = subprocess.Popen(
            [str(venv_python()), str(gui_script)],
            cwd=str(HERE),
        )
        sys.exit(proc.wait())
    os.execv(str(venv_python()), [str(venv_python()), str(gui_script)])


def main():
    gui_mode = "--gui" in sys.argv

    print("=" * 56)
    print("  SUNO BACKUP -- One-Click Setup & Launcher")
    print("=" * 56)
    print(f"\n  Platform : {platform.system()} {platform.machine()}")
    if gui_mode:
        print("  Mode     : GUI")

    print("\n[1/4] Checking Python...")
    check_python()
    print("\n[2/4] Virtual environment...")
    create_venv()
    print("\n[3/4] Installing requirements...")
    install_requirements()
    print("\n[4/4] Playwright browser...")
    install_playwright()

    if gui_mode:
        launch_gui()
    else:
        launch()


if __name__ == "__main__":
    main()

