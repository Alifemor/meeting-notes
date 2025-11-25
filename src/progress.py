# src/progress.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional

ProgressCallback = Callable[[str, int, str], None]
# stage, percent (0-100, or -1 for indeterminate), message


@dataclass
class ProgressReporter:
    callback: Optional[ProgressCallback] = None

    def report(self, stage: str, percent: int, message: str = "") -> None:
        if self.callback:
            try:
                self.callback(stage, percent, message)
            except Exception:
                # Ignore callback failures so the pipeline does not crash.
                pass
