# Meeting Notes

## Версия
**v0.9.0-beta**

**Meeting Notes** — локальное настольное приложение для транскрибации рабочих встреч, интервью и обсуждений с возможностью генерации summary.  

Транскрибация выполняется **полностью локально**.  
Во внешние сервисы отправляется **только текст транскрипта**, и только если включено summary.

---

## Возможности

- Извлечение аудио из видео через встроенный **ffmpeg**.
- Полностью локальная транскрибация через **whisper.cpp**.
- Генерация `*_summary.md` через выбранную LLM (OpenAI-совместимый API).
- Режимы:
  - **Только транскрипт**
  - **Только summary**
  - **Summary + транскрипт**
- Автоматический чанкинг длинных транскриптов.
- Офлайн работа(если summary отключено).
- Графический интерфейс с выбором моделей и настроек.

---

## Зачем это нужно

Для рабочих созвонов, интервью и внутренних встреч, где важны:

- приватность  
- безопасность  
- соблюдение NDA  

Аудио и транскрипты остаются на вашем устройстве.

---

## Установка и запуск

1. Скачайте архив последнего релиза.
2. Распакуйте в удобную папку.
3. Запустите:

```
MeetingNotes.exe
```

В дистрибутив входят:
- `bin/ffmpeg.exe`
- `bin/whisper-cli.exe`
- стандартные модели whisper (в сборку добавлены ggml-small.bin / ggml-base.bin)  
- дефолтный prompt (`prompts/summary_default.txt`)

---

### Добавление модели

1. Перейдите:  
   https://github.com/ggerganov/whisper.cpp/releases
2. Скачайте файл `ggml-*.bin`.  
3. Поместите в папку `models/` рядом с приложением.
4. Выберите модель в настройках → Advanced → Whisper model.

---

## Prompt для summary

Приложение использует следующий приоритет:

1. Пользовательский prompt, выбранный в UI.
2. Файл из `settings.json` (`summary_prompt`).
3. `prompts/summary_default.txt` (fallback).

Если выбранный файл не найден — автоматически используется дефолтный prompt.

---

## Использование 

1. Запустите приложение.
2. Выберите медиафайл (`mp4`, `mkv`, `avi`, `mov`, `mp3`, `wav`, …).
3. Выберите режимы вывода:
   - Generate summary (.md)
   - Save transcript (.txt)
4. Если требуется summary — укажите API ключ.
5. Нажмите **Start**.

Итоговые файлы сохраняются рядом с источником:

- `<имя>_transcript.txt`
- `<имя>_summary.md`

---

## Конфигурация

### `settings.json` — общие настройки

```json
{
  "ffmpeg_path": "bin/ffmpeg.exe",
  "whisper_path": "bin/whisper-cli.exe",
  "whisper_model": "models/ggml-small.bin",

  "openrouter_model": "openai/gpt-4.1-nano",
  "summary_max_tokens": 1024,
  "summary_prompt": "prompts/summary_default.txt",

  "chunk_threshold_words": 4000,
  "chunk_max_words": 3500,
  "chunk_overlap_words": 200
}
```

### `settings_user.json` — пользовательские данные

```json
{
  "openrouter_api_key": "sk-or-***"
}
```

Поддерживаются любые провайдеры, совместимые с OpenAI API:
- OpenAI
- OpenRouter (рекомендуется)
- Cloudflare Workers AI
- Together / Groq / AnyScale


---

## CLI (опционально)

```bash
python -m src.cli "video.mp4" --lang ru
python -m src.cli "video.mp4" --summary
python -m src.cli "video.mp4" --summary --with-transcript
python -m src.cli "video.mp4" --model models/ggml-base.bin
python -m src.cli "video.mp4" --model models/ggml-small.bin
```

---

## Ограничения

- Скорость транскрипции зависит от процессора.  
- Для слабых ПК рекомендуется сменить модель на ggml-small.bin 
- Whisper-модели занимают от 50 МБ до 3 ГБ.  
- Для summary требуется API-ключ LLM-провайдера.

---

## Планы развития

- Выбор LLM-провайдера и модели прямо в UI.  
- Поддержка локальных LLM через llama.cpp.  
- Расширенные параметры Whisper.  
- Продвинутая сегментация аудио и авто-улучшение транскриптов.  
- Улучшенный прогрессбар и статус операций.  
- Автоматическая проверка обновлений клиента и моделей.

---

## Лицензия

**Open-source.**  
Используйте и модифицируйте под свои задачи.
