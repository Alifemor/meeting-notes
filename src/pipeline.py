from __future__ import annotations
from pathlib import Path
import shutil
import tempfile
import time
import traceback
import re
from threading import Event

from .config import load_settings, PROJECT_ROOT
from .audio_extractor import extract_audio, AudioExtractionError, is_audio_file
from .transcriber import transcribe_audio, TranscriptionError
from .summarizer import generate_llm_summary_markdown, LLMConfigError, LLMSummaryError
from .chunker import summarize_transcript_with_chunking, ChunkingError
from .logger import setup_logger
from .progress import ProgressReporter


class ProcessingError(Exception):
    pass


# --------- helpers for resolving paths ---------


def _search_in_bases(rel: Path) -> Path | None:
    """
    Ищем относительный путь в типичных базовых каталогах:
    - PROJECT_ROOT (dev или dist/MeetingNotes)
    - PROJECT_ROOT/_internal (PyInstaller 6+)
    - текущая рабочая директория
    """
    bases = [
        PROJECT_ROOT,
        PROJECT_ROOT / "_internal",
        Path.cwd(),
    ]
    for base in bases:
        candidate = base / rel
        if candidate.is_file():
            return candidate
    return None


def resolve_whisper_model_path(model: str | None) -> Path:
    """
    Резолвит путь к модели Whisper:

    - поддерживает абсолютные пути;
    - пути относительно PROJECT_ROOT / PROJECT_ROOT/_internal / CWD;
    - 'ggml-small.bin' -> ищем в models/, _internal/models/;
    - если путь пустой/битый — используем дефолт:
      prompts/models/ggml-small.bin или первую .bin в models.
    """
    name = (model or "").strip()
    candidates: list[Path] = []

    if name and name.lower() not in ("default", "none"):
        raw = Path(name)

        if raw.is_absolute():
            candidates.append(raw)
        else:
            # как есть: models/ggml-small.bin, bin/что-нибудь и т.п.
            c = _search_in_bases(raw)
            if c:
                candidates.append(c)

            # если указано только имя файла — пробуем models/<name>
            if not raw.parent:
                for base in (PROJECT_ROOT, PROJECT_ROOT / "_internal"):
                    candidates.append(base / "models" / raw.name)

    # дефолты — на случай пустого/битого пути
    for base in (PROJECT_ROOT, PROJECT_ROOT / "_internal"):
        models_dir = base / "models"
        if models_dir.is_dir():
            default = models_dir / "ggml-small.bin"
            if default.is_file():
                candidates.append(default)
            else:
                # первая попавшаяся .bin
                for f in sorted(models_dir.glob("*.bin")):
                    candidates.append(f)
                    break

    # выбираем первый существующий
    seen: set[Path] = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        if c.is_file():
            return c

    raise ProcessingError(
        "Файл модели Whisper не найден. "
        "Проверьте настройки 'whisper_model' и содержимое папки models."
    )


def resolve_prompt_path(prompt: str | None) -> Path:
    """
    Резолвит путь к prompt-файлу.

    Если путь пустой/битый — используем дефолт:
    prompts/summary_default.txt (в PROJECT_ROOT или _internal).
    """
    name = (prompt or "").strip()
    candidates: list[Path] = []

    if name and name.lower() not in ("default", "none"):
        raw = Path(name)
        if raw.is_absolute():
            candidates.append(raw)
        else:
            c = _search_in_bases(raw)
            if c:
                candidates.append(c)

    # дефолтный prompt
    default_rel = Path("prompts") / "summary_default.txt"
    for base in (PROJECT_ROOT, PROJECT_ROOT / "_internal"):
        candidates.append(base / default_rel)

    for c in candidates:
        if c.is_file():
            return c

    raise ProcessingError(
        "Prompt-файл для summary не найден. "
        "Проверьте настройку 'summary_prompt' и наличие prompts/summary_default.txt."
    )


def resolve_whisper_binary_path(path: str | None) -> str:
    """
    Резолвит путь к whisper-cli:

    - учитывает PROJECT_ROOT / _internal / CWD;
    - если не нашли, возвращаем исходную строку (вдруг он в PATH).
    """
    name = (path or "").strip()
    if not name:
        name = "bin/whisper-cli.exe"  # разумный дефолт для нашего проекта

    raw = Path(name)
    if raw.is_absolute() and raw.is_file():
        return str(raw)

    c = _search_in_bases(raw)
    if c:
        return str(c)

    # не нашли — пусть subprocess попробует через PATH
    return name


def _unique_path(base_path: Path) -> Path:
    """
    Если файл существует — добавляем суффикс (1), (2), ...
    Например: test_summary.md -> test_summary(1).md
    """
    if not base_path.exists():
        return base_path

    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent

    i = 1
    while True:
        candidate = parent / f"{stem}({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def _md_to_text(md: str) -> str:
    """
    Очень простая "плоская" конвертация markdown в txt.
    """
    text = md
    text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


def process_video(
    video_path: Path,
    language: str | None = None,
    keep_temp: bool = False,
    summary_only: bool = False,
    with_transcript: bool = False,
    progress: ProgressReporter | None = None,
    cancel_event: Event | None = None,
    summary_format: str | None = None,   # md/txt, None -> взять из settings
) -> Path:
    progress = progress or ProgressReporter()
    cancel_event = cancel_event or Event()
    logger = setup_logger(PROJECT_ROOT / "logs", log_level="INFO", to_console=True)
    t0 = time.time()

    stage_percents = {
        "start": 0,
        "prepare": 5,
        "extract_done": 25,
        "transcribe_done": 70,
        "summary_done": 90,
        "save": 95,
        "done": 100,
    }

    def check_cancel(stage: str):
        if cancel_event.is_set():
            logger.info("Cancelled at stage: %s", stage)
            raise ProcessingError("Cancelled by user")

    def report(stage: str, percent: int, message: str):
        progress.report(stage, percent, message)

    def call_with_optional_cancel(fn, *, cancel_event, **kwargs):
        """
        Вспомогательный вызов: если тестовые моки не принимают cancel_event,
        пробуем без него.
        """
        try:
            return fn(cancel_event=cancel_event, **kwargs)
        except TypeError:
            return fn(**kwargs)

    logger.info("Start processing: %s", video_path)
    report("start", stage_percents["start"], f"Processing {video_path.name}")

    settings = load_settings()

    ffmpeg_path = settings["ffmpeg_path"]
    whisper_path_raw = settings["whisper_path"]
    whisper_model_raw = settings.get("whisper_model", "models/ggml-small.bin")
    temp_dir_setting = settings.get("temp_dir")

    openrouter_api_key = settings.get("openrouter_api_key")
    openrouter_model = settings.get("openrouter_model", "openai/gpt-4.1-mini")
    summary_max_tokens = int(settings.get("summary_max_tokens", 1024))
    summary_prompt_raw = settings.get("summary_prompt")

    long_threshold_words = int(settings.get("chunk_threshold_words", 4000))
    max_words_per_chunk = int(settings.get("chunk_max_words", 3500))
    overlap_words = int(settings.get("chunk_overlap_words", 200))

    # summary format normalize
    fmt = (summary_format or settings.get("summary_format", "md") or "md").lower()
    if fmt not in ("md", "txt"):
        fmt = "md"

    # Резолвим реальные пути
    whisper_path = resolve_whisper_binary_path(whisper_path_raw)
    model_path = resolve_whisper_model_path(whisper_model_raw)
    prompt_path = resolve_prompt_path(summary_prompt_raw)

    logger.info(
        "Settings:"
        " whisper_model_raw=%s, model_path=%s,"
        " whisper_path_raw=%s, whisper_path_resolved=%s,"
        " ffmpeg_path=%s, llm_model=%s,"
        " chunk_threshold=%s, chunk_size=%s, overlap=%s,"
        " summary_format=%s, prompt_path=%s",
        whisper_model_raw, model_path,
        whisper_path_raw, whisper_path,
        ffmpeg_path, openrouter_model,
        long_threshold_words, max_words_per_chunk, overlap_words,
        fmt, prompt_path,
    )

    # TEMP DIR (с поддержкой temp_dir из настроек)
    if temp_dir_setting:
        temp_root = Path(temp_dir_setting)
        temp_root.mkdir(parents=True, exist_ok=True)
        temp_dir = temp_root / "meeting_notes_temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = Path(tempfile.mkdtemp(prefix="meeting_notes_"))

    try:
        media_path = video_path

        report("prepare", stage_percents["prepare"], "Preparing media")
        check_cancel("prepare")

        # Detect audio or video
        if is_audio_file(media_path):
            logger.info("Input is audio, skipping ffmpeg extraction.")
            audio_path = media_path
            intermediate_dir = temp_dir
            report("extract_audio_done", stage_percents["extract_done"], "Audio ready")
        else:
            report("extract_audio", -1, "Extracting audio with ffmpeg")
            t_extract = time.time()

            audio_path = extract_audio(media_path, ffmpeg_path, temp_dir, cancel_event)
            report("extract_audio_done", stage_percents["extract_done"], "Audio extracted")

            logger.info("Audio extracted to %s in %.2fs", audio_path, time.time() - t_extract)
            check_cancel("extract_audio_done")
            intermediate_dir = audio_path.parent

        # Transcription
        report("transcribe", -1, "Transcribing with whisper")
        t_transcribe = time.time()

        transcript_tmp = call_with_optional_cancel(
            transcribe_audio,
            cancel_event=cancel_event,
            audio_path=audio_path,
            whisper_path=whisper_path,
            model_path=model_path,
            language=language,
            output_dir=intermediate_dir,
        )

        logger.info(
            "Transcription done in %.2fs. Temp transcript: %s",
            time.time() - t_transcribe, transcript_tmp
        )
        report("transcribe_done", stage_percents["transcribe_done"], "Transcription done")
        check_cancel("transcribe_done")

        final_transcript_base = media_path.with_name(f"{media_path.stem}_transcript.txt")
        final_transcript = _unique_path(final_transcript_base)

        # Summary mode
        if summary_only:
            check_cancel("before_summary")
            report("summary", -1, "Generating summary with LLM")
            t_sum = time.time()

            text = transcript_tmp.read_text(encoding="utf-8", errors="ignore")
            words = text.split()

            if len(words) > long_threshold_words:
                logger.info("Long transcript detected (%s words) -> chunking ON", len(words))
                summary_md = call_with_optional_cancel(
                    summarize_transcript_with_chunking,
                    cancel_event=cancel_event,
                    transcript_text=text,
                    language=language,
                    api_key=openrouter_api_key,
                    model=openrouter_model,
                    max_tokens=summary_max_tokens,
                    prompt_path=str(prompt_path),
                    max_words_per_chunk=max_words_per_chunk,
                    overlap_words=overlap_words,
                )
            else:
                logger.info("Short transcript (%s words) -> chunking OFF", len(words))
                summary_md = call_with_optional_cancel(
                    generate_llm_summary_markdown,
                    cancel_event=cancel_event,
                    transcript_text=text,
                    language=language,
                    api_key=openrouter_api_key,
                    model=openrouter_model,
                    max_tokens=summary_max_tokens,
                    prompt_path=str(prompt_path),
                )

            logger.info("Summary generated in %.2fs", time.time() - t_sum)
            check_cancel("summary_done")

            report("summary_done", stage_percents["summary_done"], "Summary ready")
            report("save", stage_percents["save"], "Saving result files")

            ext = "md" if fmt == "md" else "txt"
            final_summary_base = media_path.with_name(f"{media_path.stem}_summary.{ext}")
            final_summary = _unique_path(final_summary_base)

            if fmt == "md":
                final_summary.write_text(summary_md, encoding="utf-8", errors="ignore")
            else:
                summary_txt = _md_to_text(summary_md)
                final_summary.write_text(summary_txt, encoding="utf-8", errors="ignore")

            if with_transcript:
                shutil.copy2(transcript_tmp, final_transcript)
                logger.info("Transcript saved: %s", final_transcript)

            result_path = final_summary

        else:
            report("save", stage_percents["save"], "Saving transcript")
            shutil.copy2(transcript_tmp, final_transcript)
            logger.info("Transcript saved: %s", final_transcript)
            result_path = final_transcript

        report("done", stage_percents["done"], "Done")
        logger.info("Finished in %.2fs. Result: %s", time.time() - t0, result_path)
        return result_path

    except (AudioExtractionError, TranscriptionError, LLMConfigError, LLMSummaryError, ChunkingError) as e:
        logger.error("Processing error: %s", e)
        logger.debug(traceback.format_exc())
        raise ProcessingError(str(e))

    except ProcessingError:
        logger.error("Processing error")
        logger.debug(traceback.format_exc())
        raise

    except Exception as e:
        logger.error("Unexpected error: %s", e)
        logger.debug(traceback.format_exc())
        raise ProcessingError(f"Unexpected error: {e}")

    finally:
        if not keep_temp:
            shutil.rmtree(temp_dir, ignore_errors=True)
