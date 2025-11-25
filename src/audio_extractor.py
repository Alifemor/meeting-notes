from __future__ import annotations
from pathlib import Path
import subprocess
import tempfile
import time
from threading import Event
from collections import deque


class AudioExtractionError(Exception):
    """Ошибки при извлечении аудио из медиафайла."""
    pass


AUDIO_EXTENSIONS = {
    ".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus",
}


def is_audio_file(path: Path) -> bool:
    """Проверяет расширение: является ли файл аудио, а не видео."""
    return path.suffix.lower() in AUDIO_EXTENSIONS


def extract_audio(
    video_path: Path,
    ffmpeg_path: str,
    temp_dir: Path | None = None,
    cancel_event: Event | None = None,
) -> Path:
    """
    Извлекает аудиодорожку из видео в WAV 16kHz mono.
    Возвращает путь к временному аудиофайлу.
    Отслеживает cancel_event и останавливает ffmpeg при отмене.
    """
    if not video_path.is_file():
        raise AudioExtractionError(f"Файл не найден: {video_path}")

    if temp_dir is None:
        tmp_dir = Path(tempfile.mkdtemp(prefix="meeting_notes_"))
    else:
        tmp_dir = temp_dir
        tmp_dir.mkdir(parents=True, exist_ok=True)

    audio_path = tmp_dir / (video_path.stem + "_audio.wav")

    cmd = [
        ffmpeg_path,
        "-y",
        "-i", str(video_path),
        "-ac", "1",
        "-ar", "16000",
        "-af", "loudnorm",
        "-vn",
        str(audio_path),
    ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,      # stdout нам не нужен
            stderr=subprocess.PIPE,         # stderr читаем, чтобы не завис
            text=True,
            bufsize=1,                      # построчно
            universal_newlines=True,
        )
    except FileNotFoundError:
        raise AudioExtractionError(
            f"ffmpeg не найден по пути '{ffmpeg_path}'. "
            "Проверьте ffmpeg в PATH или укажите путь в settings.json."
        )

    last_lines: deque[str] = deque(maxlen=40)

    try:
        assert process.stderr is not None
        while True:
            # читаем строку (если её нет — readline вернёт '')
            line = process.stderr.readline()
            if line:
                last_lines.append(line.rstrip())

            # проверка отмены
            if cancel_event and cancel_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise AudioExtractionError(
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

    if process.returncode != 0 or not audio_path.is_file():
        tail = "\n".join(last_lines)
        raise AudioExtractionError(
            f"Ошибка ffmpeg (код {process.returncode}).\n{tail}"
        )

    return audio_path
