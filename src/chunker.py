# src/chunker.py
from __future__ import annotations
from typing import List
from threading import Event

from .summarizer import (
    generate_llm_summary_markdown,
    LLMConfigError,
    LLMSummaryError,
)


class ChunkingError(Exception):
    """Ошибка, связанная с разбиением и сборкой чанков."""
    pass


def _check_cancel(cancel_event: Event | None):
    if cancel_event and cancel_event.is_set():
        raise ChunkingError("Отменено пользователем.")


def split_text_into_chunks(
    text: str,
    max_words: int = 3500,
    overlap_words: int = 200,
    min_last_chunk_ratio: float = 0.3,
) -> List[str]:
    """
    Разбивает текст на чанки по max_words слов с перекрытием overlap_words.

    Гарантии:
    - покрываем ВСЮ последовательность слов без дыр;
    - перекрытие реализовано за счёт шага < max_words;
    - если последний чанк слишком маленький (по min_last_chunk_ratio),
      он приклеивается к предыдущему, чтобы не получать микрочанк.
    """
    words = text.split()
    n = len(words)

    if n == 0:
        return []

    if n <= max_words:
        return [text]

    # корректируем параметры
    if max_words <= 0:
        raise ChunkingError("max_words должен быть > 0")

    overlap_words = max(0, min(overlap_words, max_words - 1))
    step = max_words - overlap_words
    if step <= 0:
        step = max_words

    # сначала считаем индексы (start, end), чтобы не было дыр
    ranges: list[tuple[int, int]] = []
    start = 0
    while start < n:
        end = min(start + max_words, n)
        ranges.append((start, end))
        if end >= n:
            break
        start += step

    # если последний чанк слишком маленький — сливаем его с предыдущим
    if len(ranges) >= 2:
        last_start, last_end = ranges[-1]
        prev_start, prev_end = ranges[-2]
        last_len = last_end - last_start

        if last_len < int(max_words * min_last_chunk_ratio):
            # расширяем предпоследний чанк до конца текста
            ranges[-2] = (prev_start, last_end)
            ranges.pop()

    # собираем текстовые чанки
    chunks: List[str] = []
    for start, end in ranges:
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))

    return chunks


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
    Делает многошаговое резюме длинной транскрипции:
    1) Делит текст на чанки по max_words_per_chunk слов (с перекрытием).
    2) Для каждого чанка делает мини-summary.
    3) Объединяет мини-summary в финальное summary.

    Весь исходный текст гарантированно попадает либо в один чанк,
    либо в совокупность чанков (без дыр и потерь хвоста).
    """
    _check_cancel(cancel_event)

    try:
        chunks = split_text_into_chunks(
            transcript_text,
            max_words=max_words_per_chunk,
            overlap_words=overlap_words,
        )
    except Exception as e:
        raise ChunkingError(f"Ошибка разбиения текста на чанки: {e}")

    # Если получился один чанк — идём по обычному пути без усложнений
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

    # Немного i18n для промптов частичных summary
    lang = (language or "").lower()
    is_en = lang.startswith("en")

    mini_summaries: List[str] = []

    for idx, chunk in enumerate(chunks, start=1):
        _check_cancel(cancel_event)

        if is_en:
            part_header = (
                f"This is part {idx} of {len(chunks)} of a long meeting transcript. "
                "Create a concise summary only for THIS part, preserving the meaning."
            )
            prefix_title = f"### Part {idx}\n\n"
        else:
            part_header = (
                f"Это часть {idx} из {len(chunks)} транскрипта длинной встречи. "
                "Сделай краткое summary только по этой части, сохраняя смысл."
            )
            prefix_title = f"### Часть {idx}\n\n"

        part_text = f"{part_header}\n\n{chunk}"

        mini_md = generate_llm_summary_markdown(
            transcript_text=part_text,
            language=language,
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            prompt_path=prompt_path,
            cancel_event=cancel_event,
        )

        mini_summaries.append(prefix_title + mini_md.strip())

    # Финальное объединяющее summary
    if is_en:
        merge_intro = (
            "Below are concise summaries of parts of a long meeting. "
            "Combine them into a single final summary, avoid repetition, "
            "preserve context and key decisions."
        )
    else:
        merge_intro = (
            "Ниже собраны краткие summary частей длинной встречи. "
            "Собери единое финальное summary, избегая повтора и сохраняя контекст "
            "и ключевые решения."
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
