from __future__ import annotations

import argparse
import sys
from pathlib import Path

from services.app_config import AppConfig, ExportRuntimeSettings, load_app_config
from services.models import ExportStats, SourceCheckStats
from services.source_parser import validate_source

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_FILENAME = "ankisensei.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AnkiSensei command-line tools")
    subparsers = parser.add_subparsers(dest="command")

    export_parser = subparsers.add_parser(
        "export-apkg",
        help="Export Anki APKG using JSON configuration with optional CLI overrides",
    )
    export_parser.add_argument(
        "--config",
        help="JSON config file path. Defaults to ankisensei.json beside run.py",
    )
    export_parser.add_argument(
        "--source",
        help="Source sentence file path (UTF-8). Overrides [paths].source",
    )
    export_parser.add_argument(
        "--output",
        help="Output APKG path. Overrides [paths].apkg_output",
    )
    export_parser.add_argument(
        "--audio-dir",
        help="Audio output directory. Overrides [paths].audio_dir",
    )
    export_parser.add_argument(
        "--voice",
        help="TTS voice name. Overrides [tts].voice",
    )
    export_parser.add_argument(
        "--concurrency",
        type=int,
        help="Maximum concurrent audio generation tasks. Overrides [tts].concurrency",
    )
    export_parser.add_argument(
        "--force-audio",
        action="store_true",
        help="Regenerate all audio files even if they already exist",
    )
    export_parser.add_argument(
        "--deck-name",
        help="Anki deck name. Overrides [export].deck_name",
    )
    export_parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate source format only. Do not generate audio or APKG.",
    )
    return parser


def resolve_export_settings(
    args: argparse.Namespace,
    cwd: Path | None = None,
    project_root: Path | None = None,
) -> ExportRuntimeSettings:
    current_dir = cwd or Path.cwd()
    root_dir = project_root or PROJECT_ROOT
    config_path = _resolve_config_path(args.config, current_dir, root_dir)
    config = _load_base_config(config_path, config_required=bool(args.config))

    source = _resolve_cli_path(args.source, current_dir) or config.source
    output = _resolve_cli_path(args.output, current_dir) or config.output
    audio_dir = _resolve_cli_path(args.audio_dir, current_dir) or config.audio_dir
    deck_name = args.deck_name or config.deck_name
    voice = args.voice or config.voice
    concurrency = args.concurrency if args.concurrency is not None else config.concurrency

    if source is None:
        raise ValueError(
            'No source path configured. Set "paths.source" in the JSON config or pass --source.'
        )
    if concurrency < 1:
        raise ValueError("Concurrency must be at least 1.")
    if not args.check_only and output is None:
        raise ValueError(
            'No APKG output path configured. Set "paths.apkg_output" in the JSON config or pass --output.'
        )
    if not args.check_only and audio_dir is None:
        raise ValueError(
            'No audio output directory configured. Set "paths.audio_dir" in the JSON config or pass --audio-dir.'
        )

    return ExportRuntimeSettings(
        config_path=config_path if config_path.exists() else None,
        source=source,
        output=output,
        audio_dir=audio_dir,
        deck_name=deck_name,
        voice=voice,
        concurrency=concurrency,
        force_audio=bool(args.force_audio),
        check_only=bool(args.check_only),
        layout=config.layout,
    )


def run_export_apkg(args: argparse.Namespace) -> int:
    try:
        settings = resolve_export_settings(args)
        if settings.check_only:
            check_stats = validate_source(settings.source)
            _print_check_summary(check_stats, settings.source)
            return 0

        from services.anki_exporter import export_apkg_from_source
        assert settings.output is not None
        assert settings.audio_dir is not None

        stats = export_apkg_from_source(
            source_path=settings.source,
            output_path=settings.output,
            audio_dir=settings.audio_dir,
            voice=settings.voice,
            concurrency=settings.concurrency,
            force_audio=settings.force_audio,
            deck_name=settings.deck_name,
            layout=settings.layout,
        )
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    _print_summary(stats)
    return 0


def _resolve_config_path(raw_path: str | None, cwd: Path, project_root: Path) -> Path:
    if raw_path:
        return _resolve_cli_path(raw_path, cwd)
    return project_root / DEFAULT_CONFIG_FILENAME


def _load_base_config(config_path: Path, config_required: bool) -> AppConfig:
    if config_path.exists():
        return load_app_config(config_path)
    if config_required:
        raise FileNotFoundError(f"Config file not found: {config_path}")
    return AppConfig(config_path=config_path)


def _resolve_cli_path(raw_path: str | None, cwd: Path) -> Path | None:
    if raw_path is None:
        return None
    raw = raw_path.strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    return cwd / path


def _print_summary(stats: ExportStats) -> None:
    print("[OK] APKG export completed")
    print(f"- sentences: {stats.total_sentences}")
    print(f"- audio files: {stats.unique_audio_files}")
    print(f"- audio generated: {stats.audio_generated}")
    print(f"- audio skipped: {stats.audio_skipped}")
    print(f"- output: {stats.output_path}")


def _print_check_summary(stats: SourceCheckStats, source_path: Path) -> None:
    print("[OK] Source check completed")
    print(f"- source: {source_path}")
    print(f"- sentences: {stats.total_sentences}")
    print(f"- audio files: {stats.unique_audio_files}")
    print(f"- modules: {stats.unique_modules}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "export-apkg":
        return run_export_apkg(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
