from __future__ import annotations

import re
from pathlib import Path

from services.models import SentenceRecord, SourceCheckStats

SOURCE_LINE_PATTERN = re.compile(
    r"^(?P<jp>.+?)\s*\[sound:(?P<audio>[^\]]+)\]\s*(?P<zh>.+)$"
)
FURIGANA_PATTERN = re.compile(r"\uFF08[^\uFF09]*\uFF09|\([^)]*\)")
ANNOTATED_TERM_PATTERN = re.compile(
    r"(?P<term_fw>[^\s\uFF08\uFF09\(\)]+)\uFF08(?P<reading_fw>[^\uFF09]+)\uFF09"
    r"|(?P<term_hw>[^\s\uFF08\uFF09\(\)]+)\((?P<reading_hw>[^)]+)\)"
)
LEADING_KANA_PATTERN = re.compile(r"^[\u3041-\u3096\u30A1-\u30FA\u30FC]+")
CORE_TERM_PATTERN = re.compile(r"[\u4E00-\u9FFFA-Za-z0-9]")
NOTE_SPLIT_PATTERN = re.compile(r"\s*[|;\uFF1B]\s*")
TSV_AUDIO_SUFFIX_PATTERN = re.compile(
    r"^(?P<notes>.*?)\s*(?P<audio>(?:\[sound:[^\]]+\]|[^\s\]]+\.mp3))\s*$"
)


def parse_sentence_source(source_path: Path) -> list[SentenceRecord]:
    if not source_path.exists():
        raise FileNotFoundError(f"Sentence source file not found: {source_path}")

    records: list[SentenceRecord] = []
    current_module = "industry"
    audio_to_owner: dict[str, tuple[str, int]] = {}

    with source_path.open("r", encoding="utf-8") as file:
        for line_no, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                continue

            if is_module_heading(line):
                current_module = line
                continue

            record = _parse_data_line(line, line_no, current_module)
            previous_owner = audio_to_owner.get(record.audio_filename)
            if previous_owner is not None and previous_owner[0] != record.jp_plain:
                owner_plain, owner_line = previous_owner
                raise ValueError(
                    f"Audio filename conflict for '{record.audio_filename}'. "
                    f"Line {owner_line} maps to '{owner_plain}', "
                    f"but line {line_no} maps to '{record.jp_plain}'."
                )
            audio_to_owner.setdefault(record.audio_filename, (record.jp_plain, line_no))
            records.append(record)

    if not records:
        raise ValueError("No valid sentence records were found in source file.")

    return records


def validate_source(source_path: Path) -> SourceCheckStats:
    records = parse_sentence_source(source_path)
    return SourceCheckStats(
        total_sentences=len(records),
        unique_audio_files=len({record.audio_filename for record in records}),
        unique_modules=len({record.module for record in records}),
    )


def strip_furigana(jp_furigana: str) -> str:
    plain = FURIGANA_PATTERN.sub("", jp_furigana)
    return re.sub(r"\s+", " ", plain).strip()


def build_furigana_list_html(jp_furigana: str) -> str:
    entries = _collect_annotated_entries(jp_furigana)
    if not entries:
        return jp_furigana
    return "<br>".join(entries)


def normalize_annotated_term(term: str) -> str:
    if not term:
        return term
    original = term
    term = term.lstrip("|;\uFF1B")
    if CORE_TERM_PATTERN.search(term):
        term = LEADING_KANA_PATTERN.sub("", term)
    term = term.strip()
    return term or original


def is_module_heading(line: str) -> bool:
    normalized = line.strip()
    return normalized.startswith("\u6A21\u5757") or normalized.lower().startswith(
        "module"
    )


def module_to_tag(module: str) -> str:
    normalized = (module.strip() or "industry").lower()
    normalized = normalized.replace("\uFF1A", ":")
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^\w\-:]", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "industry"


def _parse_data_line(line: str, line_no: int, current_module: str) -> SentenceRecord:
    parts = [part.strip() for part in line.split("\t")]
    if len(parts) in (4, 5):
        return _parse_tsv_record(parts, line_no, current_module)

    repaired_parts = _repair_tsv_parts(parts)
    if repaired_parts is not None:
        return _parse_tsv_record(repaired_parts, line_no, current_module)

    if len(parts) > 1:
        raise ValueError(
            f"Line {line_no} has {len(parts)} tab-separated columns. "
            "Expected JP<TAB>NOTES<TAB>AUDIO<TAB>ZH[<TAB>TTS_TEXT]."
        )

    return _parse_legacy_record(line, line_no, current_module)


def _parse_tsv_record(
    parts: list[str],
    line_no: int,
    current_module: str,
) -> SentenceRecord:
    jp_sentence, note_list, audio_raw, zh = parts[:4]
    tts_text_override = parts[4] if len(parts) == 5 else None
    audio_filename = _normalize_audio_filename(audio_raw, line_no)

    if not jp_sentence:
        raise ValueError(f"Line {line_no} has empty Japanese text.")
    if not zh:
        raise ValueError(f"Line {line_no} has empty Chinese meaning.")

    return SentenceRecord(
        line_no=line_no,
        module=current_module,
        jp_furigana=jp_sentence,
        jp_plain=jp_sentence,
        notes_raw=note_list,
        furigana_list_html=_build_note_list_html(note_list),
        zh=zh,
        audio_filename=audio_filename,
        tts_text_override=tts_text_override or None,
    )


def _parse_legacy_record(line: str, line_no: int, current_module: str) -> SentenceRecord:
    match = SOURCE_LINE_PATTERN.match(line)
    if match is None:
        raise ValueError(
            f"Line {line_no} has invalid format. Expected either: "
            "JP<TAB>NOTES<TAB>AUDIO<TAB>ZH[<TAB>TTS_TEXT] or "
            "JP_FURIGANA[sound:FILE.mp3] ZH_MEANING"
        )

    jp_furigana = match.group("jp").strip()
    audio_filename = _normalize_audio_filename(match.group("audio").strip(), line_no)
    zh = match.group("zh").strip()

    if not jp_furigana:
        raise ValueError(f"Line {line_no} has empty Japanese text.")
    if not zh:
        raise ValueError(f"Line {line_no} has empty Chinese meaning.")

    jp_plain = strip_furigana(jp_furigana)
    if not jp_plain:
        raise ValueError(
            f"Line {line_no} produced empty plain Japanese after removing furigana."
        )

    return SentenceRecord(
        line_no=line_no,
        module=current_module,
        jp_furigana=jp_furigana,
        jp_plain=jp_plain,
        notes_raw=jp_furigana,
        furigana_list_html=build_furigana_list_html(jp_furigana),
        zh=zh,
        audio_filename=audio_filename,
    )


def _build_note_list_html(note_list: str) -> str:
    stripped = note_list.strip()
    if not stripped:
        return ""

    annotated_entries = _collect_annotated_entries(stripped)
    if annotated_entries:
        return "<br>".join(annotated_entries)

    entries = [entry.strip() for entry in NOTE_SPLIT_PATTERN.split(stripped) if entry.strip()]
    return "<br>".join(entries)


def _repair_tsv_parts(parts: list[str]) -> list[str] | None:
    if len(parts) != 3:
        return None

    jp_sentence, note_and_audio, zh = parts
    match = TSV_AUDIO_SUFFIX_PATTERN.match(note_and_audio)
    if match is None:
        return None

    notes = match.group("notes").strip()
    audio_raw = match.group("audio").strip()
    if not jp_sentence or not notes or not zh:
        return None

    return [jp_sentence, notes, audio_raw, zh]


def _collect_annotated_entries(text: str) -> list[str]:
    entries: list[str] = []
    for match in ANNOTATED_TERM_PATTERN.finditer(text):
        term = normalize_annotated_term(
            (match.group("term_fw") or match.group("term_hw") or "").strip()
        )
        reading = (match.group("reading_fw") or match.group("reading_hw") or "").strip()
        if term and reading:
            entries.append(f"{term}\uFF08{reading}\uFF09")
    return entries


def _normalize_audio_filename(audio_raw: str, line_no: int) -> str:
    audio_filename = audio_raw.strip()
    if audio_filename.startswith("[sound:") and audio_filename.endswith("]"):
        audio_filename = audio_filename[7:-1].strip()

    if not audio_filename:
        raise ValueError(f"Line {line_no} has empty audio filename.")
    if not audio_filename.lower().endswith(".mp3"):
        raise ValueError(
            f"Line {line_no} uses unsupported audio file '{audio_filename}'. "
            "Only .mp3 is supported."
        )
    return audio_filename
