# src/cli.py
from __future__ import annotations
from pathlib import Path
import argparse
import sys

from .pipeline import process_video, ProcessingError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Meeting Notes: транскрипт и summary на базе whisper.cpp и OpenRouter"
    )
    parser.add_argument(
        "video",
        help="Путь к видео- или аудиофайлу",
    )
    parser.add_argument(
        "--lang",
        dest="language",
        default=None,
        help="Язык для whisper (например, 'ru' или 'en'). "
             "Если не указан, whisper попытается определить автоматически.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Не удалять временные файлы (для отладки).",
    )
    parser.add_argument(
        "--summary",
        dest="summary_only",
        action="store_true",
        help="Сгенерировать summary.md через LLM (OpenRouter) вместо транскрипта.",
    )
    parser.add_argument(
        "--with-transcript",
        dest="with_transcript",
        action="store_true",
        help="Сохранить транскрипт рядом с файлом, даже если делаем summary.",
    )
    parser.add_argument(
    "--summary-format",
    dest="summary_format",
    choices=["md", "txt"],
    default=None,
    help="Формат summary: md (по умолчанию) или txt. Работает только с --summary.",
    )

    args = parser.parse_args(argv)

    video_path = Path(args.video).expanduser().resolve()
    if not video_path.is_file():
        print(f"Файл не найден: {video_path}", file=sys.stderr)
        return 1

    try:
        result_path = process_video(
            video_path=video_path,
            language=args.language,
            keep_temp=args.keep_temp,
            summary_only=args.summary_only,
            with_transcript=args.with_transcript,
            summary_format=args.summary_format,   # NEW
        )
        
    except ProcessingError as e:
        print(f"Ошибка обработки: {e}", file=sys.stderr)
        return 1

    print(f"Готово. Результат: {result_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
