# src/summarizer.py
from __future__ import annotations
import json
from pathlib import Path
from threading import Event
from openai import OpenAI


class LLMConfigError(Exception):
    pass


class LLMSummaryError(Exception):
    pass


def _check_cancel(cancel_event: Event | None):
    if cancel_event and cancel_event.is_set():
        raise LLMSummaryError("Отменено пользователем.")


def load_prompt(prompt_path: str) -> str:
    """
    Загружает содержимое prompt из файла.
    Если файл не найден — ошибка.
    """
    path = Path(prompt_path)
    if not path.is_file():
        raise LLMConfigError(f"Prompt-файл не найден: {prompt_path}")

    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise LLMConfigError(f"Не удалось прочитать prompt: {e}")


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
    Генерирует Markdown summary с помощью OpenRouter.
    Отменяется, если cancel_event выставлен до запроса.
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

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Вот транскрипт встречи. Сделай краткое резюме по смыслу.\n\n"
                        + transcript_text
                    )
                },
            ],
        )
    except Exception as e:
        raise LLMSummaryError(f"Ошибка запроса в OpenRouter: {e}")

    _check_cancel(cancel_event)

    try:
        md = response.choices[0].message.content
        if not md:
            raise ValueError("Пустой content в ответе.")
        return md.strip()
    except Exception as e:
        raise LLMSummaryError(f"Ошибка разбора ответа OpenRouter: {e}")


def call_openrouter_chat(api_key: str, model: str, messages: list[dict],
                         max_tokens: int = 80, temperature: float = 0):
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

    r = requests.post(url, headers=headers, json=payload, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"OpenRouter error {r.status_code}: {r.text}")

    data = r.json()
    return data["choices"][0]["message"]["content"]
