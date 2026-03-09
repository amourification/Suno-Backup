"""
test_core.py — Unit tests for the Suno Backup Tool core utilities
==================================================================
Works whether this file lives at project root or in a tests/ subfolder.

Run from the project root:
    python test_core.py
    python -m pytest test_core.py -v
If the file is in tests/:  python -m pytest tests/test_core.py -v
"""

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

# Project root: same directory as this file, or parent if this file is in tests/
_root = Path(__file__).resolve().parent
if _root.name == "tests":
    _root = _root.parent
sys.path.insert(0, str(_root))

import pytest

# ── Import helpers under test ─────────────────────────────────────────────────
from suno_backup import sanitize
from scanner     import _extract_ids_from_html, _flatten_song, export_csv, export_id_list
from vault       import save_tokens, load_tokens, is_token_fresh, clear_vault
import config

# ═══════════════════════════════════════════════════════════════════
# sanitize()
# ═══════════════════════════════════════════════════════════════════

class TestSanitize:
    def test_strips_illegal_windows_chars(self):
        assert sanitize('My Song: "A/B\\C"') == "My_Song_ABC"

    def test_collapses_whitespace(self):
        assert sanitize("  hello   world  ") == "hello_world"

    def test_truncates_to_max_len(self):
        long = "A" * 200
        result = sanitize(long)
        assert len(result) <= 80

    def test_empty_string_returns_untitled(self):
        assert sanitize("") == "untitled"

    def test_only_illegal_chars_returns_untitled(self):
        assert sanitize('\\/*?:"<>|') == "untitled"

    def test_unicode_preserved(self):
        assert sanitize("النهر الفضي") == "النهر_الفضي"

    def test_normal_title_unchanged(self):
        assert sanitize("MyTrack") == "MyTrack"

    def test_numbers_preserved(self):
        assert sanitize("Track 42") == "Track_42"


# ═══════════════════════════════════════════════════════════════════
# _extract_ids_from_html()
# ═══════════════════════════════════════════════════════════════════

SAMPLE_UUID   = "43b0804d-6d26-495f-a2a9-04216f793465"
SAMPLE_UUID_2 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

class TestExtractIdsFromHtml:
    def test_finds_image_jpeg_pattern(self):
        html = f'<img src="https://cdn1.suno.ai/image_{SAMPLE_UUID}.jpeg">'
        assert SAMPLE_UUID in _extract_ids_from_html(html)

    def test_finds_webm_pattern(self):
        html = f'<source src="https://cdn1.suno.ai/{SAMPLE_UUID}.webm">'
        assert SAMPLE_UUID in _extract_ids_from_html(html)

    def test_finds_mp3_pattern(self):
        html = f'<audio src="https://cdn1.suno.ai/{SAMPLE_UUID}.mp3">'
        assert SAMPLE_UUID in _extract_ids_from_html(html)

    def test_finds_song_href(self):
        html = f'<a href="/song/{SAMPLE_UUID}">Listen</a>'
        assert SAMPLE_UUID in _extract_ids_from_html(html)

    def test_finds_json_id_field(self):
        html = f'"id": "{SAMPLE_UUID}"'
        assert SAMPLE_UUID in _extract_ids_from_html(html)

    def test_finds_multiple_ids(self):
        html = (
            f'<img src="image_{SAMPLE_UUID}.jpeg">'
            f'<source src="{SAMPLE_UUID_2}.webm">'
        )
        found = _extract_ids_from_html(html)
        assert SAMPLE_UUID   in found
        assert SAMPLE_UUID_2 in found

    def test_empty_html_returns_empty_set(self):
        assert _extract_ids_from_html("") == set()

    def test_no_ids_in_plain_text(self):
        assert _extract_ids_from_html("Hello world! No IDs here.") == set()

    def test_normalises_to_lowercase(self):
        html = f'"id": "{SAMPLE_UUID.upper()}"'
        found = _extract_ids_from_html(html)
        assert SAMPLE_UUID.lower() in found

    def test_does_not_match_short_non_uuid(self):
        html = '"id": "1234-5678"'
        assert _extract_ids_from_html(html) == set()


# ═══════════════════════════════════════════════════════════════════
# _flatten_song()
# ═══════════════════════════════════════════════════════════════════

class TestFlattenSong:
    def _make_song(self, **overrides):
        base = {
            "id":          SAMPLE_UUID,
            "title":       "Test Track",
            "display_name":"Test Track Display",
            "status":      "complete",
            "duration":    180,
            "created_at":  "2024-01-01T00:00:00Z",
            "audio_url":   f"https://cdn1.suno.ai/{SAMPLE_UUID}.mp3",
            "image_url":   f"https://cdn1.suno.ai/image_{SAMPLE_UUID}.jpeg",
            "model_name":  "chirp-v3",
            "tags":        "pop, upbeat",
            "is_public":   True,
            "play_count":  42,
            "upvote_count": 7,
        }
        base.update(overrides)
        return base

    def test_id_extracted(self):
        row = _flatten_song(self._make_song())
        assert row["id"] == SAMPLE_UUID

    def test_title_extracted(self):
        row = _flatten_song(self._make_song())
        assert row["title"] == "Test Track"

    def test_wav_url_computed_from_id(self):
        row = _flatten_song(self._make_song())
        assert row["wav_url"] == f"{config.CDN_BASE}/{SAMPLE_UUID}.wav"

    def test_video_url_fallback_to_webm(self):
        song = self._make_song()
        song.pop("video_url", None)
        row = _flatten_song(song)
        assert row["video_url"] == f"{config.CDN_BASE}/{SAMPLE_UUID}.webm"

    def test_image_large_url_fallback_to_cdn(self):
        song = self._make_song()
        song.pop("image_large_url", None)
        row = _flatten_song(song)
        assert row["image_large_url"] == f"{config.CDN_BASE}/image_{SAMPLE_UUID}.jpeg"

    def test_metadata_tags_fallback(self):
        song = self._make_song()
        del song["tags"]
        song["metadata"] = {"tags": "ambient"}
        row = _flatten_song(song)
        assert row["tags"] == "ambient"

    def test_empty_song_no_crash(self):
        row = _flatten_song({})
        assert row["id"] == ""
        assert row["wav_url"] == ""

    def test_source_field_preserved(self):
        song = self._make_song()
        song["_source"] = "dom_scan+api_enrich"
        row = _flatten_song(song)
        assert row["source"] == "dom_scan+api_enrich"


# ═══════════════════════════════════════════════════════════════════
# export_csv() and export_id_list()
# ═══════════════════════════════════════════════════════════════════

class TestExportFunctions:
    def _sample_songs(self):
        return [
            {"id": SAMPLE_UUID,   "title": "Track A", "_source": "api_feed",
             "audio_url": "https://cdn.example.com/a.mp3"},
            {"id": SAMPLE_UUID_2, "title": "Track B", "_source": "api_feed"},
        ]

    def test_export_csv_creates_file(self, tmp_path):
        csv_path = tmp_path / "out.csv"
        n = export_csv(self._sample_songs(), csv_path)
        assert csv_path.exists()
        assert n == 2

    def test_export_csv_deduplicates(self, tmp_path):
        songs = self._sample_songs() + [{"id": SAMPLE_UUID, "title": "Duplicate"}]
        n = export_csv(songs, tmp_path / "out.csv")
        assert n == 2

    def test_export_csv_has_header(self, tmp_path):
        csv_path = tmp_path / "out.csv"
        export_csv(self._sample_songs(), csv_path)
        text = csv_path.read_text()
        assert "id" in text
        assert "title" in text
        assert "wav_url" in text

    def test_export_id_list(self, tmp_path):
        ids = [SAMPLE_UUID, SAMPLE_UUID_2]
        p   = tmp_path / "ids.txt"
        export_id_list(ids, p)
        lines = [l for l in p.read_text().splitlines() if l]
        assert set(lines) == set(ids)

    def test_export_id_list_deduplicates(self, tmp_path):
        ids = [SAMPLE_UUID, SAMPLE_UUID, SAMPLE_UUID_2]
        p   = tmp_path / "ids.txt"
        export_id_list(ids, p)
        lines = [l for l in p.read_text().splitlines() if l]
        assert len(lines) == 2


# ═══════════════════════════════════════════════════════════════════
# vault  (save/load with a temporary directory)
# ═══════════════════════════════════════════════════════════════════

class TestVault:
    """
    Tests redirect VAULT_FILE and SALT_FILE to a temp dir so they
    never touch the real vault on disk.
    """

    def _patch_vault_paths(self, tmp_path):
        """Return a context-manager that redirects vault paths."""
        import vault as vault_mod
        import config as config_mod
        vault_file = tmp_path / ".test_vault"
        salt_file  = tmp_path / ".test_salt"
        return (
            patch.multiple(vault_mod, VAULT_FILE=vault_file, SALT_FILE=salt_file),
            patch.multiple(config_mod, VAULT_FILE=vault_file, SALT_FILE=salt_file),
        )

    def test_save_and_load_roundtrip(self, tmp_path):
        import vault as vault_mod
        vault_file = tmp_path / ".test_vault"
        salt_file  = tmp_path / ".test_salt"
        with patch.object(vault_mod, "VAULT_FILE", vault_file), \
             patch.object(vault_mod, "SALT_FILE",  salt_file):
            data = {"authorization": "Bearer test123", "_saved_at": time.time()}
            vault_mod.save_tokens(data)
            loaded = vault_mod.load_tokens()
        assert loaded is not None
        assert loaded["authorization"] == "Bearer test123"

    def test_load_returns_none_if_no_file(self, tmp_path):
        import vault as vault_mod
        vault_file = tmp_path / ".missing_vault"
        salt_file  = tmp_path / ".missing_salt"
        with patch.object(vault_mod, "VAULT_FILE", vault_file), \
             patch.object(vault_mod, "SALT_FILE",  salt_file):
            assert vault_mod.load_tokens() is None

    def test_load_returns_none_on_corrupted_file(self, tmp_path):
        import vault as vault_mod
        vault_file = tmp_path / ".corrupt_vault"
        salt_file  = tmp_path / ".corrupt_salt"
        vault_file.write_bytes(b"this is not valid fernet data!!!!")
        with patch.object(vault_mod, "VAULT_FILE", vault_file), \
             patch.object(vault_mod, "SALT_FILE",  salt_file):
            assert vault_mod.load_tokens() is None

    def test_clear_vault_removes_files(self, tmp_path):
        import vault as vault_mod
        vault_file = tmp_path / ".v"
        salt_file  = tmp_path / ".s"
        vault_file.write_text("x")
        salt_file.write_text("y")
        with patch.object(vault_mod, "VAULT_FILE", vault_file), \
             patch.object(vault_mod, "SALT_FILE",  salt_file):
            vault_mod.clear_vault()
        assert not vault_file.exists()
        assert not salt_file.exists()

    def test_is_token_fresh_true_when_recent(self):
        tokens = {"_saved_at": time.time()}
        assert is_token_fresh(tokens, max_age_sec=3000) is True

    def test_is_token_fresh_false_when_old(self):
        tokens = {"_saved_at": time.time() - 4000}
        assert is_token_fresh(tokens, max_age_sec=3000) is False

    def test_is_token_fresh_false_when_missing_timestamp(self):
        assert is_token_fresh({}, max_age_sec=3000) is False


# ═══════════════════════════════════════════════════════════════════
# Runner (allows: python tests/test_core.py)
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import unittest

    # Collect and run all test classes without pytest
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    for cls in [TestSanitize, TestExtractIdsFromHtml, TestFlattenSong,
                TestExportFunctions, TestVault]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
