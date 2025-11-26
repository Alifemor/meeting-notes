# src/summarizer.py
from __future__ import annotations
import json
import unicodedata
from pathlib import Path
from threading import Event
from openai import OpenAI


# ------------------ exceptions ------------------

class LLMConfigError(Exception):
    pass


class LLMSummaryError(Exception):
    pass


# ------------------ helpers ------------------

def _norm(p: str | Path) -> str:
    """
    Приводит путь к NFC, чтобы избежать падений на Unicode-символах.
    """
    return unicodedata.normalize("NFC", str(p))


def _check_cancel(cancel_event: Event | None):
    if cancel_event and cancel_event.is_set():
        raise LLMSummaryError("Отменено пользователем.")


def load_prompt(prompt_path: str) -> str:
    """
    Загружает prompt из файла. С поддержкой Unicode-путей.
    """
    if not prompt_path:
        raise LLMConfigError("Путь к prompt-файлу пустой.")

    path = Path(_norm(prompt_path))

    if not path.is_file():
        raise LLMConfigError(f"Prompt-файл не найден: {prompt_path}")

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if not text.strip():
            raise ValueError("Prompt-файл пустой.")
        return text
    except Exception as e:
        raise LLMConfigError(f"Не удалось прочитать prompt '{prompt_path}': {e}")


# ------------------ main summary function ------------------

def generate_llm_summary_markdown(
    transcript_text: str,
    language: str | None,
    api_key: str,
    model: str,
    max_tokens: int,
    prompt_path: str | None = None,
    cancel_event: Event | None = None,
) -> str:
    """
    Создаёт Markdown-summary через OpenRouter.
    """

    if not api_key:
        raise LLMConfigError("OpenRouter API key не задан (openrouter_api_key).")

    if not prompt_path:
        raise LLMConfigError("Путь к prompt-файлу не задан (summary_prompt).")

    system_prompt = load_prompt(prompt_path)

    _check_cancel(cancel_event)

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    user_text = (
        "Вот транскрипт встречи. Сформируй лаконичное смысловое резюме.\n\n"
        + transcript_text
    )

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        )
    except Exception as e:
        raise LLMSummaryError(f"Ошибка запроса в OpenRouter: {e}")

    _check_cancel(cancel_event)

    # Разбираем ответ
    try:
        choice = response.choices[0]
        md = choice.message.content

        if not md:
            raise ValueError("Пустой content в ответе.")

        return str(md).strip()

    except Exception as e:
        raise LLMSummaryError(f"Ошибка разбора ответа OpenRouter: {e}")


# ------------------ lightweight chat tester (LLM Test in GUI) ------------------

def call_openrouter_chat(
    api_key: str,
    model: str,
    messages: list[dict],
    max_tokens: int = 80,
    temperature: float = 0,
):
    """
    Прямой HTTP-запрос к OpenRouter для теста LLM.
    """
    import requests

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
    except Exception as e:
        raise RuntimeError(f"Ошибка обращения к OpenRouter: {e}")

    if r.status_code != 200:
        raise RuntimeError(f"OpenRouter error {r.status_code}: {r.text}")

    try:
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Ошибка разбора ответа OpenRouter: {e}")
