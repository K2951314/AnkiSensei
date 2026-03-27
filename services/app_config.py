from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LAYOUT_SECTION_NAMES = {"sentence", "notes", "audio", "translation"}


@dataclass(frozen=True)
class LayoutConfig:
    front_sections: tuple[str, ...] = ("sentence", "notes", "audio")
    front_answer_sections: tuple[str, ...] = ("translation",)
    reverse_front_sections: tuple[str, ...] = ("translation",)
    reverse_back_sections: tuple[str, ...] = ("sentence", "notes", "audio")
    font_family: str = '"Noto Sans JP", "Microsoft YaHei", sans-serif'
    base_font_size: int = 24
    sentence_font_size: int = 30
    notes_font_size: int = 22
    answer_font_size: int = 30
    card_text_color: str = "#1f2933"
    card_background_color: str = "#ffffff"
    notes_color: str = "#3b4b5a"
    sentence_line_height: float = 1.45
    notes_line_height: float = 1.8
    answer_line_height: float = 1.6
    page_padding_top: int = 20
    page_padding_side: int = 16
    page_padding_bottom: int = 28
    sentence_margin_top: int = 12
    audio_padding_top: int = 18


@dataclass(frozen=True)
class AppConfig:
    config_path: Path
    source: Path | None = None
    output: Path | None = None
    audio_dir: Path | None = None
    deck_name: str = "AnkiSensei"
    voice: str = "ja-JP-NanamiNeural"
    concurrency: int = 5
    layout: LayoutConfig = field(default_factory=LayoutConfig)


@dataclass(frozen=True)
class ExportRuntimeSettings:
    config_path: Path | None
    source: Path
    output: Path | None
    audio_dir: Path | None
    deck_name: str
    voice: str
    concurrency: int
    force_audio: bool
    check_only: bool
    layout: LayoutConfig


def load_app_config(config_path: Path) -> AppConfig:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    raw_text = config_path.read_text(encoding="utf-8").strip()
    raw_config = json.loads(raw_text) if raw_text else {}
    if not isinstance(raw_config, dict):
        raise ValueError("Config file must contain a JSON object at the top level.")

    base_dir = config_path.parent
    paths = _expect_object(raw_config.get("paths"), "paths")
    export = _expect_object(raw_config.get("export"), "export")
    tts = _expect_object(raw_config.get("tts"), "tts")
    layout = _expect_object(raw_config.get("layout"), "layout")

    resolved_layout = LayoutConfig(
        front_sections=_load_sections(
            layout.get("front_sections"), LayoutConfig.front_sections
        ),
        front_answer_sections=_load_sections(
            layout.get("front_answer_sections"), LayoutConfig.front_answer_sections
        ),
        reverse_front_sections=_load_sections(
            layout.get("reverse_front_sections"), LayoutConfig.reverse_front_sections
        ),
        reverse_back_sections=_load_sections(
            layout.get("reverse_back_sections"), LayoutConfig.reverse_back_sections
        ),
        font_family=_get_string(layout, "font_family", LayoutConfig.font_family),
        base_font_size=_get_int(layout, "base_font_size", LayoutConfig.base_font_size),
        sentence_font_size=_get_int(
            layout, "sentence_font_size", LayoutConfig.sentence_font_size
        ),
        notes_font_size=_get_int(layout, "notes_font_size", LayoutConfig.notes_font_size),
        answer_font_size=_get_int(
            layout, "answer_font_size", LayoutConfig.answer_font_size
        ),
        card_text_color=_get_string(
            layout, "card_text_color", LayoutConfig.card_text_color
        ),
        card_background_color=_get_string(
            layout,
            "card_background_color",
            LayoutConfig.card_background_color,
        ),
        notes_color=_get_string(layout, "notes_color", LayoutConfig.notes_color),
        sentence_line_height=_get_float(
            layout, "sentence_line_height", LayoutConfig.sentence_line_height
        ),
        notes_line_height=_get_float(
            layout, "notes_line_height", LayoutConfig.notes_line_height
        ),
        answer_line_height=_get_float(
            layout, "answer_line_height", LayoutConfig.answer_line_height
        ),
        page_padding_top=_get_int(
            layout, "page_padding_top", LayoutConfig.page_padding_top
        ),
        page_padding_side=_get_int(
            layout, "page_padding_side", LayoutConfig.page_padding_side
        ),
        page_padding_bottom=_get_int(
            layout, "page_padding_bottom", LayoutConfig.page_padding_bottom
        ),
        sentence_margin_top=_get_int(
            layout, "sentence_margin_top", LayoutConfig.sentence_margin_top
        ),
        audio_padding_top=_get_int(
            layout, "audio_padding_top", LayoutConfig.audio_padding_top
        ),
    )

    return AppConfig(
        config_path=config_path,
        source=_resolve_optional_path(paths.get("source"), base_dir, "paths.source"),
        output=_resolve_optional_path(
            paths.get("apkg_output"), base_dir, "paths.apkg_output"
        ),
        audio_dir=_resolve_optional_path(
            paths.get("audio_dir"), base_dir, "paths.audio_dir"
        ),
        deck_name=_get_string(export, "deck_name", "AnkiSensei"),
        voice=_get_string(tts, "voice", "ja-JP-NanamiNeural"),
        concurrency=_get_int(tts, "concurrency", 5),
        layout=resolved_layout,
    )


def _expect_object(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f'"{name}" must be a JSON object.')
    return value


def _resolve_optional_path(value: Any, base_dir: Path, field_name: str) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string path.")
    raw = value.strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    return base_dir / path


def _load_sections(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    if not isinstance(value, list):
        raise ValueError("Layout section lists must be JSON arrays.")

    sections: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise ValueError("Layout section names must be strings.")
        name = entry.strip()
        if name not in LAYOUT_SECTION_NAMES:
            raise ValueError(f"Unknown layout section: {name}")
        sections.append(name)

    if not sections:
        raise ValueError("Layout section lists must not be empty.")
    return tuple(sections)


def _get_string(table: dict[str, Any], key: str, default: str) -> str:
    value = table.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string.")
    return value


def _get_int(table: dict[str, Any], key: str, default: int) -> int:
    value = table.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer.")
    return value


def _get_float(table: dict[str, Any], key: str, default: float) -> float:
    value = table.get(key)
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number.")
    return float(value)
