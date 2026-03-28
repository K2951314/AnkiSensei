from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

import genanki

from services.app_config import LayoutConfig
from services.audio_cache import (
    build_audio_fingerprint_from_normalized,
    build_manifest_entry,
    is_audio_current,
    load_audio_manifest,
    save_audio_manifest,
)
from services.models import ExportStats, SentenceRecord
from services.source_parser import module_to_tag, parse_sentence_source
from services.tts_service import generate_audio
from services.tts_text import apply_notes_reading_overrides, normalize_tts_text


@dataclass(frozen=True)
class AudioJob:
    audio_filename: str
    normalized_text: str
    fingerprint: str
    output_path: Path


def export_apkg_from_source(
    source_path: Path,
    output_path: Path,
    audio_dir: Path,
    voice: str = "ja-JP-NanamiNeural",
    concurrency: int = 5,
    force_audio: bool = False,
    deck_name: str = "AnkiSensei",
    layout: LayoutConfig | None = None,
) -> ExportStats:
    records = parse_sentence_source(source_path)

    generated, skipped = asyncio.run(
        _ensure_audio_files(
            records=records,
            audio_dir=audio_dir,
            voice=voice,
            concurrency=max(1, concurrency),
            force_audio=force_audio,
        )
    )

    unique_audio_files = sorted({record.audio_filename for record in records})
    media_paths = [audio_dir / audio_file for audio_file in unique_audio_files]
    missing_files = [
        path.name for path in media_paths if not path.exists() or path.stat().st_size <= 0
    ]
    if missing_files:
        raise RuntimeError(
            f"Audio generation incomplete. Missing files: {', '.join(missing_files[:5])}"
        )

    model = _build_anki_model(layout)
    deck = genanki.Deck(_stable_anki_id(f"deck::{deck_name}"), deck_name)

    for record in records:
        note = genanki.Note(
            model=model,
            fields=[
                record.jp_plain,
                record.jp_furigana,
                record.furigana_list_html,
                record.zh,
                f"[sound:{record.audio_filename}]",
            ],
            tags=[module_to_tag(record.module)],
            guid=build_note_guid(record),
        )
        deck.add_note(note)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    package = genanki.Package(deck)
    package.media_files = [str(path) for path in media_paths]
    package.write_to_file(str(output_path))

    return ExportStats(
        total_sentences=len(records),
        unique_audio_files=len(unique_audio_files),
        audio_generated=generated,
        audio_skipped=skipped,
        output_path=output_path,
    )


def build_audio_jobs(
    records: list[SentenceRecord],
    audio_dir: Path,
    voice: str,
    force_audio: bool,
) -> tuple[list[AudioJob], int]:
    manifest_entries = load_audio_manifest(audio_dir)
    filename_to_record: dict[str, SentenceRecord] = {}
    for record in records:
        filename_to_record.setdefault(record.audio_filename, record)

    jobs: list[AudioJob] = []
    skipped = 0

    for audio_filename, record in sorted(filename_to_record.items()):
        base = record.tts_text_override or record.jp_plain
        if not record.tts_text_override:
            base = apply_notes_reading_overrides(base, record.notes_raw)
        normalized_text = normalize_tts_text(base)
        fingerprint = build_audio_fingerprint_from_normalized(normalized_text, voice)
        if not force_audio and is_audio_current(
            audio_dir,
            audio_filename,
            fingerprint,
            voice,
            manifest_entries,
        ):
            skipped += 1
            continue
        jobs.append(
            AudioJob(
                audio_filename=audio_filename,
                normalized_text=normalized_text,
                fingerprint=fingerprint,
                output_path=audio_dir / audio_filename,
            )
        )

    return jobs, skipped


def build_note_guid(record: SentenceRecord) -> str:
    return genanki.guid_for(record.module, record.jp_plain)


async def _ensure_audio_files(
    records: list[SentenceRecord],
    audio_dir: Path,
    voice: str,
    concurrency: int,
    force_audio: bool,
) -> tuple[int, int]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    jobs, skipped = build_audio_jobs(records, audio_dir, voice, force_audio)
    manifest_entries = load_audio_manifest(audio_dir)
    generated = 0
    semaphore = asyncio.Semaphore(concurrency)

    async def create_one(job: AudioJob) -> None:
        nonlocal generated
        async with semaphore:
            await generate_audio(job.normalized_text, str(job.output_path), voice)
        manifest_entries[job.audio_filename] = build_manifest_entry(
            job.fingerprint,
            voice,
        )
        generated += 1

    await asyncio.gather(*(create_one(job) for job in jobs))
    save_audio_manifest(audio_dir, manifest_entries)
    return generated, skipped


def _build_anki_model(layout: LayoutConfig | None = None) -> genanki.Model:
    resolved_layout = layout or LayoutConfig()
    return genanki.Model(
        model_id=_stable_anki_id("model::ankisensei_bilingual_v1"),
        name="AnkiSensei Bilingual Model v1",
        fields=[
            {"name": "JP_PLAIN"},
            {"name": "JP_FURIGANA"},
            {"name": "FURIGANA_LIST"},
            {"name": "ZH"},
            {"name": "AUDIO"},
        ],
        templates=[
            {
                "name": "JP_to_ZH",
                "qfmt": _build_face(resolved_layout.front_sections),
                "afmt": _build_face(resolved_layout.front_answer_sections),
            },
            {
                "name": "ZH_to_JP",
                "qfmt": _build_face(resolved_layout.reverse_front_sections),
                "afmt": _build_face(resolved_layout.reverse_back_sections),
            },
        ],
        css=_build_model_css(resolved_layout),
    )


def _build_face(sections: tuple[str, ...]) -> str:
    # Keep translation-only faces vertically centered, while mixed faces render as stacked zones.
    if sections == ("translation",):
        return '<div class="answer-zone zh-answer">{{ZH}}</div>'

    rendered_sections = "".join(_render_section(section) for section in sections)
    return f'<div class="layout">{rendered_sections}</div>'


def _render_section(section: str) -> str:
    if section == "sentence":
        return '<div class="sentence-zone">{{JP_PLAIN}}</div>'
    if section == "notes":
        return '<div class="notes-zone">{{FURIGANA_LIST}}</div>'
    if section == "audio":
        return '<div class="audio-zone">{{AUDIO}}</div>'
    if section == "translation":
        return '<div class="translation-zone">{{ZH}}</div>'
    raise ValueError(f"Unsupported layout section: {section}")


def _build_model_css(layout: LayoutConfig) -> str:
    return f"""
.card {{
  font-family: {layout.font_family};
  font-size: {layout.base_font_size}px;
  text-align: center;
  color: {layout.card_text_color};
  background-color: {layout.card_background_color};
  line-height: 1.5;
  padding: 0;
  margin: 0;
}}
.layout {{
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  padding: {layout.page_padding_top}px {layout.page_padding_side}px {layout.page_padding_bottom}px;
}}
.sentence-zone {{
  font-size: {layout.sentence_font_size}px;
  font-weight: 600;
  line-height: {layout.sentence_line_height};
  margin-top: {layout.sentence_margin_top}px;
}}
.notes-zone {{
  margin-top: auto;
  margin-bottom: auto;
  font-size: {layout.notes_font_size}px;
  line-height: {layout.notes_line_height};
  color: {layout.notes_color};
  white-space: normal;
}}
.notes-zone:empty {{
  min-height: 24px;
}}
.audio-zone {{
  margin-top: auto;
  padding-top: {layout.audio_padding_top}px;
}}
.translation-zone {{
  margin-top: auto;
  margin-bottom: auto;
  font-size: {layout.answer_font_size}px;
  line-height: {layout.answer_line_height};
}}
.answer-zone {{
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  padding: 24px 18px;
}}
.zh-answer {{
  font-size: {layout.answer_font_size}px;
  line-height: {layout.answer_line_height};
}}
""".strip()


def _stable_anki_id(seed: str) -> int:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return 1_000_000_000 + (int(digest[:8], 16) % 899_999_999)
