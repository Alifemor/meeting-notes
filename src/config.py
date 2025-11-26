from __future__ import annotations
from pathlib import Path
import json
import os
import sys
import unicodedata


# ---------- helpers ----------

def _norm_path(p: Path) -> Path:
    """
    Unicode-safe нормализация пути (NFC).    
    """
    return Path(unicodedata.normalize("NFC", str(p)))


def _read_json(path: Path) -> dict:
    """
    Безопасное чтение JSON.
    При ошибке возвращаем пустой словарь.
    """
    path = _norm_path(path)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return {}


def _write_json(path: Path, data: dict) -> None:
    """
    Безопасная запись JSON с UTF-8 и нормализацией пути.
    """
    path = _norm_path(path)
    try:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        # fallback: попробовать создать каталог
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


# ---------- project root detection ----------

def _detect_project_root() -> Path:
    """
    Корректно определяет корень проекта как:

    ⬤ Dev mode:
        <repo>/src/config.py → root = parent.parent

    ⬤ PyInstaller (dist):
        sys._MEIPASS существует → root = _MEIPASS
        (в PyInstaller 6+ ваши бинарники окажутся в _internal/)
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return _norm_path(Path(sys._MEIPASS))

    return _norm_path(Path(__file__).resolve().parent.parent)


PROJECT_ROOT = _detect_project_root()


# ---------- defaults ----------

DEFAULT_SETTINGS = {
    "ffmpeg_path": "ffmpeg",
    "whisper_path": "bin/whisper-cli.exe",
    "whisper_model": "ggml-small.bin",

    "temp_dir": None,

    # LLM
    "openrouter_api_key": None,
    "openrouter_model": "openai/gpt-4.1-mini",
    "summary_max_tokens": 1024,

    # chunking
    "chunk_threshold_words": 4000,
    "chunk_max_words": 3500,
    "chunk_overlap_words": 200,

    # prompt
    "summary_prompt": "prompts/summary_default.txt",

    # summary format
    "summary_format": "md",
}


# ---------- local settings directory ----------

def _get_app_dir() -> Path:
    """
    Каталог, куда помещаются user-local настройки.
    Не зависит от расположения EXE.
    """

    if sys.platform.startswith("win"):
        base = os.getenv("LOCALAPPDATA")
        if base:
            return _norm_path(Path(base) / "MeetingNotes")

        # fallback если LOCALAPPDATA нет
        return _norm_path(Path.home() / "AppData" / "Local" / "MeetingNotes")

    # macOS / Linux
    return _norm_path(Path.home() / ".meeting-notes")


# ---------- ensure settings exist ----------

def ensure_local_settings_files() -> tuple[Path, Path]:
    """
    Создаёт, если отсутствуют:
    - AppData/Local/MeetingNotes/settings.json
    - settings_user.json (секреты)
    """

    app_dir = _get_app_dir()
    app_dir.mkdir(parents=True, exist_ok=True)

    local_settings = app_dir / "settings.json"
    user_settings = app_dir / "settings_user.json"

    # settings.json
    if not local_settings.is_file():
        example_path = PROJECT_ROOT / "settings.example.json"

        if example_path.is_file():
            base_example = _read_json(example_path)
            merged = {**DEFAULT_SETTINGS, **base_example}
            _write_json(local_settings, merged)
        else:
            _write_json(local_settings, DEFAULT_SETTINGS)

    # settings_user.json (секреты)
    if not user_settings.is_file():
        _write_json(user_settings, {})

    return local_settings, user_settings


# ---------- load final settings ----------

def load_settings() -> dict:
    """
    Загрузка настроек в порядке приоритета:

        DEFAULT
        ← settings.example.json (если есть)
        ← settings.json (AppData)
        ← settings_user.json (AppData, секреты)
    """

    local_path, user_path = ensure_local_settings_files()

    settings = DEFAULT_SETTINGS.copy()

    # settings.example.json из проекта
    example_path = PROJECT_ROOT / "settings.example.json"
    example_data = _read_json(example_path)
    if example_data:
        settings.update(example_data)

    # settings.json (user-local)
    settings.update(_read_json(local_path))

    # settings_user.json (секреты)
    settings.update(_read_json(user_path))

    return settings
