from __future__ import annotations
from pathlib import Path
import subprocess
import tempfile
import time
from threading import Event
from collections import deque
import sys


class TranscriptionError(Exception):
    """Ошибки при транскрипции аудио (whisper)."""
    pass


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

    :param audio_path: путь к WAV/MP3/… файлу
    :param whisper_path: путь к whisper-cli.exe (из settings["whisper_path"])
    :param model_path: путь к .bin модели (resolve_whisper_model_path уже сделал)
    :param language: "ru", "en" или None/auto
    :param output_dir: каталог, куда класть временный транскрипт
    :param cancel_event: если установлен — прерываем работу
    :return: Path к .txt файлу с транскриптом
    """
    if not audio_path.is_file():
        raise TranscriptionError(f"Файл аудио не найден: {audio_path}")

    if not model_path.is_file():
        raise TranscriptionError(f"Файл модели Whisper не найден: {model_path}")

    # каталог под выходные файлы whisper
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # базовое имя выходного файла (без расширения)
    base = output_dir / audio_path.stem
    txt_path = base.with_suffix(".txt")

    # язык для whisper.cpp: "auto" / "ru" / "en"
    lang = (language or "auto").lower()

    cmd = [
        whisper_path,
        "-m", str(model_path),
        "-f", str(audio_path),
        "-otxt",
        "-of", str(base),
        "-l", lang,
    ]

    # Базовые параметры Popen
    popen_kwargs = dict(
        stdout=subprocess.DEVNULL,   # вывод не читаем
        stderr=subprocess.PIPE,      # читаем stderr, чтобы не завис
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    # На Windows скрываем консольное окно whisper-cli
    if sys.platform.startswith("win"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        popen_kwargs["startupinfo"] = startupinfo
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        process = subprocess.Popen(cmd, **popen_kwargs)
    except FileNotFoundError:
        raise TranscriptionError(
            f"whisper не найден по пути '{whisper_path}'. "
            "Добавьте whisper в PATH или укажите путь в settings.json."
        )

    last_lines: deque[str] = deque(maxlen=40)

    try:
        assert process.stderr is not None

        while True:
            line = process.stderr.readline()
            if line:
                last_lines.append(line.rstrip())

            # Проверка отмены
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

    # --- ищем результат более терпимо ---
    # маленькая пауза на всякий случай, чтобы ОС успела «дописать» файл
    time.sleep(0.1)

    if not txt_path.is_file():
        # на всякий случай ищем любые *.txt от этого аудио
        candidates = sorted(output_dir.glob(f"{audio_path.stem}*.txt"))
        if candidates:
            txt_path = candidates[0]

    if process.returncode != 0 or not txt_path.is_file():
        tail = "\n".join(last_lines)
        raise TranscriptionError(
            f"Ошибка whisper (код {process.returncode}).\n{tail}"
        )

    return txt_path
