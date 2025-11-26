# src/logger.py
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def setup_logger(
    log_dir: Path,
    log_level: str = "INFO",
    to_console: bool = True,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> logging.Logger:
    """
    Создаёт логгер приложения:
    - файл с ротацией: logs/app.log
    - опционально вывод в консоль
    - безопасен при многократных вызовах (не плодит хендлеры)
    """

    # Если приложение собрано в exe — консольного окна, как правило, нет,
    # вывод в консоль тогда не особо нужен.
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        to_console = False

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.log"

    logger = logging.getLogger("meeting_notes")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.propagate = False

    # Если наш файловый хендлер уже есть — просто возвращаем логгер.
    for h in logger.handlers:
        if isinstance(h, RotatingFileHandler):
            return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logger.level)
    logger.addHandler(file_handler)

    if to_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logger.level)
        logger.addHandler(console_handler)

    return logger
