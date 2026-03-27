from __future__ import annotations

import hashlib
import json
from pathlib import Path

from services.tts_text import normalize_tts_text

AUDIO_MANIFEST_FILENAME = ".ankisensei_audio_manifest.json"
AUDIO_MANIFEST_VERSION = 1


def get_audio_manifest_path(audio_dir: Path) -> Path:
    return audio_dir / AUDIO_MANIFEST_FILENAME


def build_audio_fingerprint(text: str, voice: str) -> str:
    return build_audio_fingerprint_from_normalized(normalize_tts_text(text), voice)


def build_audio_fingerprint_from_normalized(normalized_text: str, voice: str) -> str:
    seed = f"{AUDIO_MANIFEST_VERSION}\0{voice}\0{normalized_text}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


def build_manifest_entry(fingerprint: str, voice: str) -> dict[str, str]:
    return {
        "fingerprint": fingerprint,
        "voice": voice,
    }


def load_audio_manifest(audio_dir: Path) -> dict[str, dict[str, str]]:
    manifest_path = get_audio_manifest_path(audio_dir)
    if not manifest_path.exists():
        return {}

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict) or payload.get("version") != AUDIO_MANIFEST_VERSION:
        return {}

    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, dict):
        return {}

    entries: dict[str, dict[str, str]] = {}
    for filename, entry in raw_entries.items():
        if not isinstance(filename, str) or not isinstance(entry, dict):
            continue
        fingerprint = entry.get("fingerprint")
        voice = entry.get("voice")
        if isinstance(fingerprint, str) and isinstance(voice, str):
            entries[filename] = {
                "fingerprint": fingerprint,
                "voice": voice,
            }
    return entries


def save_audio_manifest(audio_dir: Path, entries: dict[str, dict[str, str]]) -> None:
    audio_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": AUDIO_MANIFEST_VERSION,
        "entries": entries,
    }
    get_audio_manifest_path(audio_dir).write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def is_audio_current(
    audio_dir: Path,
    audio_filename: str,
    fingerprint: str,
    voice: str,
    manifest_entries: dict[str, dict[str, str]],
) -> bool:
    output_path = audio_dir / audio_filename
    if not output_path.exists() or output_path.stat().st_size <= 0:
        return False

    entry = manifest_entries.get(audio_filename)
    if entry is None:
        return False

    return entry.get("fingerprint") == fingerprint and entry.get("voice") == voice
