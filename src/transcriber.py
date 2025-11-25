from __future__ import annotations
from pathlib import Path
import subprocess
import time
from threading import Event
from collections import deque


class TranscriptionError(Exception):
    """Ошибки при вызове whisper.cpp."""
    pass


def transcribe_audio(
    audio_path: Path,
    whisper_path: str,
    model_path: Path,
    language: str | None = None,
    output_dir: Path | None = None,
    cancel_event: Event | None = None,
) -> Path:
    """
    Запускает whisper.cpp для распознавания аудио.
    Возвращает путь к итоговому .txt файлу.
    Отслеживает cancel_event и завершает процесс при отмене.
    """
    if not audio_path.is_file():
        raise TranscriptionError(f"Аудио не найдено: {audio_path}")

    if output_dir is None:
        output_dir = audio_path.parent

    output_dir.mkdir(parents=True, exist_ok=True)
    base_name = audio_path.stem
    output_base = output_dir / base_name
    transcript_path = output_dir / f"{base_name}.txt"

    cmd = [
        whisper_path,
        "-m", str(model_path),
        "-f", str(audio_path),
        "-otxt",
        "-of", str(output_base),
    ]
    if language:
        cmd.extend(["-l", language])

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            errors="ignore",
        )
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

    if process.returncode != 0 or not transcript_path.is_file():
        tail = "\n".join(last_lines)
        raise TranscriptionError(
            f"Ошибка whisper (код {process.returncode}).\n{tail}"
        )

    return transcript_path
