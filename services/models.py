from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SentenceRecord:
    line_no: int
    module: str
    jp_furigana: str
    jp_plain: str
    notes_raw: str
    furigana_list_html: str
    zh: str
    audio_filename: str
    tts_text_override: str | None = None


@dataclass(frozen=True)
class SourceCheckStats:
    total_sentences: int
    unique_audio_files: int
    unique_modules: int


@dataclass(frozen=True)
class ExportStats:
    total_sentences: int
    unique_audio_files: int
    audio_generated: int
    audio_skipped: int
    output_path: Path
