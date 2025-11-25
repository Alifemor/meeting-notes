meeting-notes/
  src/
    __init__.py
    cli.py              # входная точка (main)
    pipeline.py         # сценарий "видео -> аудио -> текст"
    audio_extractor.py  # обёртка над ffmpeg
    transcriber.py      # обёртка над whisper.cpp
    config.py           # конфиг и пути к бинарникам
  settings.example.json
  README.md