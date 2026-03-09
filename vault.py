"""
vault.py — Encrypted local token storage
=========================================
Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
The key is derived from machine-unique identifiers + a local random salt,
so the vault file is unreadable on any other machine.
"""

import base64
import hashlib
import json
import os
import platform
import secrets
import time
import uuid
from pathlib import Path

from config import VAULT_FILE, SALT_FILE, TOKEN_MAX_AGE_SEC

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


def _get_machine_secret() -> bytes:
    parts: list[str] = []
    try:
        parts.append(platform.node())
    except Exception:
        pass
    try:
        parts.append(hex(uuid.getnode()))
    except Exception:
        pass
    parts.extend([platform.system(), platform.machine()])

    if platform.system() == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\Cryptography")
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            parts.append(str(guid))
        except Exception:
            pass
    elif platform.system() == "Linux":
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                parts.append(Path(p).read_text().strip()); break
            except OSError:
                pass
    elif platform.system() == "Darwin":
        try:
            import subprocess
            out = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                                 capture_output=True, text=True, timeout=5).stdout
            for line in out.splitlines():
                if "IOPlatformSerialNumber" in line:
                    parts.append(line.split('"')[-2]); break
        except Exception:
            pass

    return hashlib.sha256("|".join(parts).encode()).digest()


def _get_or_create_salt() -> bytes:
    if SALT_FILE.exists():
        return bytes.fromhex(SALT_FILE.read_text().strip())
    salt = secrets.token_bytes(32)
    SALT_FILE.write_text(salt.hex())
    if platform.system() == "Windows":
        import subprocess
        subprocess.run(["attrib", "+H", str(SALT_FILE)], capture_output=True)
    return salt


def _derive_key() -> bytes:
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography not available — cannot derive vault key")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=_get_or_create_salt(), iterations=480_000)
    return base64.urlsafe_b64encode(kdf.derive(_get_machine_secret()))


def save_tokens(data: dict) -> None:
    """Encrypt and persist token data. Uses atomic write + retry on Windows permission errors."""
    if not CRYPTO_AVAILABLE:
        print("  ⚠  cryptography not installed — tokens stored as plain text")
        _write_vault_atomic(VAULT_FILE, json.dumps(data).encode(), text=True)
        return
    payload = Fernet(_derive_key()).encrypt(json.dumps(data).encode())
    _write_vault_atomic(VAULT_FILE, payload, text=False)
    if platform.system() == "Windows":
        import subprocess
        subprocess.run(["attrib", "+H", str(VAULT_FILE)], capture_output=True)
    print("  ✓ Tokens encrypted and saved to vault")


def _write_vault_atomic(path: Path, data: bytes, *, text: bool = False) -> None:
    """Write via temp file + replace; retry on PermissionError (e.g. Windows lock)."""
    directory = path.resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f".suno_vault_tmp_{os.getpid()}"
    write_data = data.decode("utf-8") if text else data
    mode = "w" if text else "wb"
    last_err = None
    for attempt in range(3):
        try:
            with open(tmp, mode) as f:
                f.write(write_data)
            tmp.replace(path)
            return
        except PermissionError as e:
            last_err = e
            if attempt < 2:
                time.sleep(0.3 * (attempt + 1))
            continue
        except OSError as e:
            last_err = e
            break
    if tmp.exists():
        try:
            tmp.unlink()
        except OSError:
            pass
    print("  ⚠  Could not save vault (permission denied or file in use).")
    print("     Close other Suno Backup windows and try again, or check antivirus.")
    raise last_err or OSError("Failed to write vault")


def load_tokens() -> dict | None:
    """Decrypt and return stored tokens, or None if unavailable/invalid."""
    if not VAULT_FILE.exists():
        return None
    if not CRYPTO_AVAILABLE:
        try:
            return json.loads(VAULT_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return None
    try:
        data = Fernet(_derive_key()).decrypt(VAULT_FILE.read_bytes())
        return json.loads(data.decode())
    except InvalidToken:
        print("  ⚠  Vault decryption failed (wrong machine or corrupted vault)")
        return None
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"  ⚠  Vault load error: {exc}")
        return None


def clear_vault() -> None:
    for f in (VAULT_FILE, SALT_FILE):
        if f.exists():
            f.unlink()
    print("  ✓ Vault cleared")


def is_token_fresh(tokens: dict, max_age_sec: int = TOKEN_MAX_AGE_SEC) -> bool:
    return (time.time() - tokens.get("_saved_at", 0)) < max_age_sec
