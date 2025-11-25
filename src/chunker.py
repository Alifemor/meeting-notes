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
) -> List[str]:
    """
    Разбивает текст на чанки по заданному количеству слов.
    overlap_words — перекрытие между чанками для сохранения контекста.
    """
    words = text.split()
    if len(words) <= max_words:
        return [text]

    chunks: List[str] = []
    start = 0
    n = len(words)

    while start < n:
        end = min(start + max_words, n)
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))

        if end >= n:
            break

        # перекрытие: возвращаемся на overlap_words слов назад
        start = max(0, end - overlap_words)

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
    1) Делит текст на чанки по max_words_per_chunk слов.
    2) Для каждого чанка делает мини-summary (с перекрытием контекста).
    3) Объединяет мини-summary в финальный итог.
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

    mini_summaries: List[str] = []

    for idx, chunk in enumerate(chunks, start=1):
        _check_cancel(cancel_event)

        part_header = (
            f"Это часть {idx} из {len(chunks)} транскрипта длинной встречи. "
            "Сделай краткое summary только по этой части, сохраняя смысл."
        )
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

        mini_summaries.append(f"### Часть {idx}\n\n{mini_md.strip()}")

    merge_input = (
        "Ниже собраны краткие summary частей длинной встречи. "
        "Собери единое финальное summary, избегая повтора и сохраняя контекст.\n\n"
        + "\n\n".join(mini_summaries)
    )

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
