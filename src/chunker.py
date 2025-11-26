# src/chunker.py
from __future__ import annotations
from typing import List
from threading import Event
import unicodedata

from .summarizer import (
    generate_llm_summary_markdown,
    LLMConfigError,
    LLMSummaryError,
)


# ---------------- errors ----------------

class ChunkingError(Exception):
    """Ошибка, связанная с разбиением и сборкой чанков."""
    pass


# ---------------- helpers ----------------

def _norm_text(text: str) -> str:
    """
    Unicode-normalization NFC для текстов.
    Предотвращает скрытые баги на CJK-символах.
    """
    return unicodedata.normalize("NFC", text or "")


def _check_cancel(cancel_event: Event | None):
    if cancel_event and cancel_event.is_set():
        raise ChunkingError("Отменено пользователем.")


# ---------------- chunk splitter ----------------

def split_text_into_chunks(
    text: str,
    max_words: int = 3500,
    overlap_words: int = 200,
    min_last_chunk_ratio: float = 0.3,
) -> List[str]:
    """
    Разбивает текст на чанки с перекрытием.
    Гарантировано покрывает ВСЁ содержимое текста.

    Логика:
    - шаг = max_words - overlap_words
    - последний слишком маленький чанк приклеивается к предыдущему
    """

    text = _norm_text(text)
    words = text.split()
    n = len(words)

    if n == 0:
        return []

    if n <= max_words:
        return [text]

    if max_words <= 0:
        raise ChunkingError("max_words должен быть > 0")

    overlap_words = max(0, min(overlap_words, max_words - 1))
    step = max_words - overlap_words
    if step <= 0:
        step = max_words

    ranges: list[tuple[int, int]] = []
    start = 0

    # покрываем текст вперед без дыр
    while start < n:
        end = min(start + max_words, n)
        ranges.append((start, end))
        if end >= n:
            break
        start += step

    # если хвост слишком мал — приклеиваем
    if len(ranges) >= 2:
        last_start, last_end = ranges[-1]
        last_len = last_end - last_start

        if last_len < int(max_words * min_last_chunk_ratio):
            prev_start, prev_end = ranges[-2]
            ranges[-2] = (prev_start, last_end)
            ranges.pop()

    # финальная сборка чанков
    chunks: List[str] = []
    for s, e in ranges:
        chunk = " ".join(words[s:e])
        chunks.append(chunk)

    return chunks


# ---------------- summarizing with chunking ----------------

def summarize_transcript_with_chunking(
    transcript_text: str,
    language: str | None,
    api_key: str,
    model: str,
    max_tokens: int,
    prompt_path: str,
    max_words_per_chunk: int = 3500,
    overlap_words: int = 200,
    cancel_event: Event | None = None,
) -> str:
    """
    Многошаговое резюме длинного транскрипта:

    1) Чанкинг без потерь
    2) Mini-summary по каждому чанку
    3) Итоговое summary, объединяющее все части
    """

    transcript_text = _norm_text(transcript_text)
    _check_cancel(cancel_event)

    try:
        chunks = split_text_into_chunks(
            transcript_text,
            max_words=max_words_per_chunk,
            overlap_words=overlap_words,
        )
    except Exception as e:
        raise ChunkingError(f"Ошибка разбиения текста на чанки: {e}")

    # один чанк — генерируем напрямую
    if len(chunks) == 1:
        return generate_llm_summary_markdown(
            transcript_text=transcript_text,
            language=language,
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            prompt_path=prompt_path,
            cancel_event=cancel_event,
        )

    lang = (language or "").lower()
    is_en = lang.startswith("en")

    mini_summaries: List[str] = []

    # --- mini summaries ---
    for idx, chunk in enumerate(chunks, start=1):
        _check_cancel(cancel_event)

        if is_en:
            part_header = (
                f"This is part {idx} of {len(chunks)} of a long meeting transcript. "
                "Generate a concise summary **ONLY for this part**."
            )
            part_title = f"### Part {idx}\n\n"
        else:
            part_header = (
                f"Это часть {idx} из {len(chunks)} длинной встречи. "
                "Сформируй краткое summary **только по этой части**."
            )
            part_title = f"### Часть {idx}\n\n"

        part_text = part_header + "\n\n" + chunk

        mini_md = generate_llm_summary_markdown(
            transcript_text=part_text,
            language=language,
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            prompt_path=prompt_path,
            cancel_event=cancel_event,
        )

        mini_summaries.append(part_title + mini_md.strip())

    # --- merge stage ---
    if is_en:
        merge_intro = (
            "Below are summaries of all parts of a long meeting. "
            "Merge them into a **single final summary**, avoid repetition, "
            "preserve context, decisions and structure."
        )
    else:
        merge_intro = (
            "Ниже приведены краткие summary частей встречи. "
            "Объедини их в **одно итоговое summary**, избегая повторов, "
            "сохранив контекст и ключевые решения."
        )

    merge_input = merge_intro + "\n\n" + "\n\n".join(mini_summaries)

    try:
        final_md = generate_llm_summary_markdown(
            transcript_text=merge_input,
            language=language,
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            prompt_path=prompt_path,
            cancel_event=cancel_event,
        )
    except (LLMConfigError, LLMSummaryError) as e:
        raise ChunkingError(f"Ошибка на этапе слияния чанков: {e}")

    return final_md
