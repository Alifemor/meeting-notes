from __future__ import annotations
from pathlib import Path
import subprocess
import tempfile
import time
from threading import Event
from collections import deque
import unicodedata
import sys


class TranscriptionError(Exception):
    """Ошибки при транскрипции аудио (whisper)."""
    pass


# -------------------- Unicode helper --------------------

def _norm(p: str | Path) -> str:
    """
    Нормализует путь (NFC) и приводит к str.
    Whisper-cli и subprocess иногда ломаются на сочетаниях юникодных форм.
    """
    return unicodedata.normalize("NFC", str(p))


# -------------------- Main function --------------------

def transcribe_audio(
    audio_path: Path,
    whisper_path: str,
    model_path: Path,
    language: str | None,
    output_dir: Path,
    cancel_event: Event | None = None,
) -> Path:
    """
    Запускает whisper-cli и получает текстовый транскрипт.
    """

    # нормализация путей
    audio_path = Path(_norm(audio_path)).resolve()
    model_path = Path(_norm(model_path)).resolve()
    whisper_path = _norm(whisper_path)
    output_dir = Path(_norm(output_dir))

    if not audio_path.is_file():
        raise TranscriptionError(f"Файл аудио не найден: {audio_path}")

    if not model_path.is_file():
        raise TranscriptionError(f"Файл модели Whisper не найден: {model_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # базовое имя выходного файла (без расширения)
    base = output_dir / audio_path.stem
    base_str = _norm(base)
    txt_path = Path(base_str + ".txt")

    # язык для whisper.cpp: "auto" / "ru" / "en"
    lang = (language or "auto").lower()

    # whisper-cli command
    cmd = [
        whisper_path,
        "-m", _norm(model_path),
        "-f", _norm(audio_path),
        "-otxt",
        "-of", base_str,
        "-l", lang,
    ]

    popen_kwargs = dict(
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    # скрытие консольного окна whisper-cli
    if sys.platform.startswith("win"):
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        popen_kwargs["startupinfo"] = startup
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        process = subprocess.Popen(cmd, **popen_kwargs)
    except FileNotFoundError:
        raise TranscriptionError(
            f"whisper не найден по пути '{whisper_path}'. "
            "Добавьте whisper в PATH или укажите путь в settings.json."
        )

    last_lines: deque[str] = deque(maxlen=40)

    # main read loop
    try:
        assert process.stderr is not None

        while True:
            line = process.stderr.readline()

            if line:
                # нормализуем мусор, чтобы не падать
                safe = (
                    line.rstrip("\n")
                    .encode("utf-8", errors="replace")
                    .decode("utf-8", errors="replace")
                )
                last_lines.append(safe)

            # отмена
            if cancel_event and cancel_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

                raise TranscriptionError(
                    "Отменено пользователем.\n" + "\n".join(last_lines)
                )

            ret = process.poll()
            if ret is not None:
                break

            time.sleep(0.05)

    finally:
        try:
            if process.stderr:
                process.stderr.close()
        except Exception:
            pass

    # whisper иногда пишет файл с небольшой задержкой
    time.sleep(0.1)

    # retry: whisper иногда пишет файл в конце скачком
    if not txt_path.is_file():
        for _ in range(10):
            time.sleep(0.05)
            if txt_path.is_file():
                break

    # если всё ещё нет — ищем похожие файлы
    if not txt_path.is_file():
        candidates = sorted(output_dir.glob(f"{audio_path.stem}*.txt"))
        if candidates:
            txt_path = candidates[0]

    # итоговая проверка
    if process.returncode != 0 or not txt_path.is_file():
        tail = "\n".join(last_lines)
        raise TranscriptionError(
            f"Ошибка whisper (код {process.returncode}).\n{tail}"
        )

    return txt_path
