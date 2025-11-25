# src/config.py
from __future__ import annotations
from pathlib import Path
import json
import os
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SETTINGS = {
    "ffmpeg_path": "ffmpeg",
    "whisper_path": "bin/whisper-cli.exe",
    "whisper_model": "ggml-small.bin",
    "temp_dir": None,

    # OpenRouter
    "openrouter_api_key": None,
    "openrouter_model": "openai/gpt-4.1-mini",
    "summary_max_tokens": 1024,

    # chunking defaults
    "chunk_threshold_words": 4000,
    "chunk_max_words": 3500,
    "chunk_overlap_words": 200,

    # prompt
    "summary_prompt": "prompts/summary_default.txt",
}


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def _get_app_dir() -> Path:
    """
    Куда складывать user-local настройки.
    Чтобы exe работал из Program Files и не упирался в права,
    кладём в AppData/Local/MeetingNotes.
    """
    if sys.platform.startswith("win"):
        base = Path(os.getenv("LOCALAPPDATA", str(PROJECT_ROOT)))
        return base / "MeetingNotes"
    else:
        # для mac/linux — папка в домашней директории
        return Path.home() / ".meeting-notes"


def ensure_local_settings_files() -> tuple[Path, Path]:
    """
    Гарантирует наличие локальных settings.json / settings_user.json.
    Если нет settings.json — копируем из settings.example.json или DEFAULT_SETTINGS.
    Возвращает пути к локальным файлам.
    """
    app_dir = _get_app_dir()
    app_dir.mkdir(parents=True, exist_ok=True)

    local_settings = app_dir / "settings.json"
    user_settings = app_dir / "settings_user.json"

    if not local_settings.is_file():
        example_path = PROJECT_ROOT / "settings.example.json"
        if example_path.is_file():
            base_example = _read_json(example_path)
            merged = {**DEFAULT_SETTINGS, **base_example}
            _write_json(local_settings, merged)
        else:
            _write_json(local_settings, DEFAULT_SETTINGS)

    if not user_settings.is_file():
        _write_json(user_settings, {})  # пустой файл для секретов

    return local_settings, user_settings


def load_settings() -> dict:
    """
    Загружает настройки:
    DEFAULT < settings.example.json < local settings.json < settings_user.json
    """
    local_path, user_path = ensure_local_settings_files()

    settings = DEFAULT_SETTINGS.copy()

    # example (из репо/бандла)
    example_path = PROJECT_ROOT / "settings.example.json"
    settings.update(_read_json(example_path))

    # local user-editable
    settings.update(_read_json(local_path))

    # secrets/overrides
    settings.update(_read_json(user_path))

    return settings
