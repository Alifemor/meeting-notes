from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from ttkbootstrap.constants import *

try:
    from ttkbootstrap.widgets.scrolled import ScrolledFrame
except Exception:
    ScrolledFrame = None

from src.progress import ProgressReporter
from src.config import load_settings, PROJECT_ROOT, ensure_local_settings_files


# ---------------- i18n ----------------

I18N = {
    "en": {
        "title": "Meeting Notes",
        "ui_lang": "UI language:",
        "input_file": "Input file",
        "browse": "Browse...",
        "output": "Output",
        "gen_summary": "Generate summary",
        "save_transcript": "Save transcript (.txt)",
        "summary_format": "Summary format:",
        "summary_format_md": "Markdown (.md)",
        "summary_format_txt": "Text (.txt)",
        "api_key": "API key:",
        "language": "Transcription language:",
        "lang_auto": "auto (beta)",
        "start": "Start",
        "cancel": "Cancel",
        "open_folder": "Open output folder",
        "progress": "Progress",
        "advanced_toggle": "Advanced settings",
        "advanced": "Advanced",
        "whisper_model": "Whisper model file:",
        "whisper_browse": "Browse...",
        "models_open": "Releases",
        "llm_model": "LLM model:",
        "max_tokens": "Summary max tokens:",
        "prompt_file": "Prompt file:",
        "prompt_edit": "Edit",
        "chunking": "Chunking",
        "threshold_words": "Threshold words:",
        "chunk_size_words": "Chunk size words:",
        "overlap_words": "Overlap words:",
        "chunk_help": (
            "Chunking splits long transcripts into overlapping parts.\n"
            "Threshold: when to enable chunking.\n"
            "Chunk size: max words per part.\n"
            "Overlap: words repeated between parts for context."
        ),
        "models_help": (
            "To add models:\n"
            "1) Open whisper.cpp releases:\n"
            "   https://github.com/ggerganov/whisper.cpp/releases\n"
            "2) Download a .bin model (e.g., ggml-small.bin)\n"
            "3) Put it into the 'models' folder near the app\n"
            "4) Select it here"
        ),
        "progress_help": (
            "Processing speed depends on the Whisper model, file length, CPU and other factors.\n"
            "Example: about 15 minutes for 1-hour audio or video (varies by machine)."
        ),
        "test_llm": "LLM Test",
        "test_llm_fail": "LLM test failed:\n{error}",
        "no_file": "Please select a media file.",
        "no_output": "Select at least one output: summary and or transcript.",
        "done_title": "Done",
        "done_msg": "Result saved:\n{path}",
        "error_title": "Error",
        "cancelled": "Cancelled",
        "show_api_key": "Show",
        "hide_api_key": "Hide",

        "status_idle": "Idle",
        "status_starting": "Starting...",
        "status_testing_llm": "Testing LLM...",
        "status_error": "Error",
        "status_done_prefix": "Done",

        "elapsed": "Elapsed:",
    },
    "ru": {
        "title": "Meeting Notes",
        "ui_lang": "Язык интерфейса:",
        "input_file": "Файл",
        "browse": "Выбрать...",
        "output": "Вывод",
        "gen_summary": "Сделать summary",
        "save_transcript": "Сохранить транскрипт (.txt)",
        "summary_format": "Формат summary:",
        "summary_format_md": "Markdown (.md)",
        "summary_format_txt": "Текст (.txt)",
        "api_key": "API ключ:",
        "language": "Язык транскрипции:",
        "lang_auto": "auto (beta)",
        "start": "Старт",
        "cancel": "Отмена",
        "open_folder": "Открыть папку результата",
        "progress": "Прогресс",
        "advanced_toggle": "Расширенные настройки",
        "advanced": "Расширенные",
        "whisper_model": "Файл модели Whisper:",
        "whisper_browse": "Выбрать...",
        "models_open": "Релизы",
        "llm_model": "Модель LLM:",
        "max_tokens": "Макс. токенов summary:",
        "prompt_file": "Файл prompt:",
        "prompt_edit": "Редактировать",
        "chunking": "Чанкинг",
        "threshold_words": "Порог слов:",
        "chunk_size_words": "Размер чанка (слов):",
        "overlap_words": "Перекрытие (слов):",
        "chunk_help": (
            "Чанкинг делит длинный текст на части с перекрытием.\n"
            "Порог: когда включать чанкинг.\n"
            "Размер чанка: максимум слов в части.\n"
            "Перекрытие: сколько слов повторять между частями для контекста."
        ),
        "models_help": (
            "Как добавить модели:\n"
            "1) Откройте релизы whisper.cpp:\n"
            "   https://github.com/ggerganov/whisper.cpp/releases\n"
            "2) Скачайте .bin модель (например, ggml-small.bin)\n"
            "3) Поместите файл в папку 'models' рядом с приложением\n"
            "4) Выберите её здесь"
        ),
        "progress_help": (
            "Скорость обработки зависит от модели Whisper, длительности файла, CPU и других факторов.\n"
            "Пример: около 15 минут для 1 часа аудио или видео (зависит от ПК)."
        ),
        "test_llm": "Тест LLM",
        "test_llm_fail": "Ошибка теста LLM:\n{error}",
        "no_file": "Пожалуйста, выберите медиафайл.",
        "no_output": "Выберите хотя бы один вывод: summary и или транскрипт.",
        "done_title": "Готово",
        "done_msg": "Результат сохранён:\n{path}",
        "error_title": "Ошибка",
        "cancelled": "Отменено",
        "show_api_key": "Показать",
        "hide_api_key": "Скрыть",

        "status_idle": "Ожидание",
        "status_starting": "Запуск...",
        "status_testing_llm": "Проверка LLM...",
        "status_error": "Ошибка",
        "status_done_prefix": "Готово",

        "elapsed": "Прошло:",
    }
}


# ---------------- tooltip ----------------

class ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _=None):
        if self.tip:
            return

        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + 16

        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")

        bg = "#1f1f1f"
        frame = tk.Frame(self.tip, bg=bg, bd=1, relief="solid")
        frame.pack()

        label = tk.Label(
            frame,
            text=self.text,
            justify=tk.LEFT,
            bg=bg,
            fg="#E0E0E0",
            padx=10,
            pady=8,
            font=("Segoe UI", 9)
        )
        label.pack()

    def _hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class MeetingNotesGUI(ttk.Window):
    def __init__(self):
        super().__init__(
            title="Meeting Notes",
            themename="darkly",
            size=(780, 600),
            resizable=(True, True),
        )
        self.minsize(740, 560)

        # AppUserModelID для корректной иконки в таскбаре Windows
        if sys.platform.startswith("win"):
            self._set_app_user_model_id_windows()

        # Кастомный titlebar
        self._use_custom_titlebar = True
        if self._use_custom_titlebar:
            self.overrideredirect(True)
            # Помогает корректно отображаться в таскбаре Windows
            self.after(10, lambda: self.attributes("-topmost", False))
            if sys.platform.startswith("win"):
                self.after(50, self._force_taskbar_icon_windows)

        self.settings = load_settings()
        self.cancel_event = threading.Event()
        self.is_running = False

        self.stage_ranges = {
            "extract_audio": (5, 25),
            "transcribe": (25, 70),
            "summary": (70, 90),
        }
        self._pseudo_job = None
        self._pseudo_target_to = None
        self._last_stage = None

        self.start_time = None
        self._timer_job = None
        self.elapsed_var = tk.StringVar(value="00:00")

        # Состояние UI
        self.ui_lang_var = tk.StringVar(value="ru")
        self.file_path = tk.StringVar(value="")

        # Язык транскрипции следует языку UI, пока пользователь не поменяет вручную
        self._lang_user_overridden = False
        default_transcribe = "ru" if self.ui_lang_var.get() == "ru" else "en"
        self.lang_var = tk.StringVar(value=default_transcribe)

        self.summary_var = tk.BooleanVar(value=True)
        self.transcript_var = tk.BooleanVar(value=False)
        self.summary_format_var = tk.StringVar(
            value=str(self.settings.get("summary_format", "md"))
        )

        # API / Advanced
        raw_key = str(self.settings.get("openrouter_api_key", "")).strip()
        if raw_key.lower() == "none":
            raw_key = ""
        self.api_key_var = tk.StringVar(value=raw_key)

        self.whisper_model_var = tk.StringVar(
            value=str(self.settings.get("whisper_model", "ggml-small.bin"))
        )
        self.llm_model_var = tk.StringVar(
            value=str(self.settings.get("openrouter_model", "openai/gpt-4.1-nano"))
        )
        self.max_tokens_var = tk.IntVar(
            value=int(self.settings.get("summary_max_tokens", 1024))
        )

        self.chunk_threshold_var = tk.IntVar(
            value=int(self.settings.get("chunk_threshold_words", 4000))
        )
        self.chunk_size_var = tk.IntVar(
            value=int(self.settings.get("chunk_max_words", 3500))
        )
        self.chunk_overlap_var = tk.IntVar(
            value=int(self.settings.get("chunk_overlap_words", 200))
        )

        self.prompt_path_var = tk.StringVar(
            value=str(self.settings.get("summary_prompt", "prompts/summary_default.txt"))
        )

        self.progress_var = tk.IntVar(value=0)
        self.status_var = tk.StringVar(value="")
        self.progress_indeterminate = False

        self.api_key_visible = False

        self._configure_styles()
        self._set_app_icon()
        self._build_ui()
        self._apply_i18n()
        self.status_var.set(self._t("status_idle"))
        self._update_summary_dependent_ui()

    # ---------------- Windows taskbar fix ----------------

    def _set_app_user_model_id_windows(self):
        try:
            import ctypes
            appid = "MeetingNotes.App"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
        except Exception:
            pass

    def _force_taskbar_icon_windows(self):
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())

            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080

            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style | WS_EX_APPWINDOW
            style = style & ~WS_EX_TOOLWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

            self.withdraw()
            self.after(10, self.deiconify)
        except Exception:
            pass

    # ---------------- icon ----------------

    def _set_app_icon(self):
        assets_dir = PROJECT_ROOT / "assets"
        ico_path = assets_dir / "app.ico"
        png_path = assets_dir / "app.png"

        self._titlebar_icon_img = None

        try:
            is_win = sys.platform.startswith("win")

            # Иконка окна и таскбара
            if is_win and ico_path.is_file():
                self.iconbitmap(str(ico_path))
            else:
                if png_path.is_file():
                    img = tk.PhotoImage(file=str(png_path))
                    self.iconphoto(True, img)

            if png_path.is_file():
                img = tk.PhotoImage(file=str(png_path))

                target_size = 20
                scale = max(img.width() // target_size, 1)
                if scale > 1:
                    img = img.subsample(scale, scale)

                self._titlebar_icon_img = img
        except Exception:
            pass

    # ---------------- styles ----------------

    def _configure_styles(self):
        self.option_add("*Font", ("Segoe UI", 10))

        style = self.style
        style.configure("TLabel", foreground="#E0E0E0")
        style.configure("TLabelframe.Label", foreground="#E8E8E8", font=("Segoe UI", 10, "bold"))
        style.configure("TCheckbutton", foreground="#E0E0E0")
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TEntry", font=("Segoe UI", 10))
        style.configure("TSpinbox", font=("Segoe UI", 10))
        style.configure("TCombobox", font=("Segoe UI", 10), padding=6)

        # Верхняя строка внутри контента
        style.configure("Topbar.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Topbar.TFrame", padding=(6, 4))

        # Кастомный titlebar
        titlebar_bg = "#1b1b1b"
        titlebar_hover_bg = "#2a2a2a"

        style.configure(
            "Titlebar.TFrame",
            bootstyle="dark",
            padding=(8, 6),
            background=titlebar_bg
        )

        style.configure(
            "Titlebar.TLabel",
            font=("Segoe UI", 10, "bold"),
            background=titlebar_bg
        )

        style.configure(
            "Titlebar.TButton",
            font=("Segoe UI", 11, "bold"),
            padding=(0, 0),
            anchor="center",
            background=titlebar_bg,
            foreground="#E0E0E0",
            borderwidth=0,
            relief="flat",
            focuscolor=titlebar_bg,
            highlightthickness=0
        )
        style.map(
            "Titlebar.TButton",
            background=[("active", titlebar_hover_bg)],
            foreground=[("active", "#FFFFFF")],
            relief=[("active", "flat")]
        )

    # ---------------- entry shortcuts + context menu ----------------


    def _bind_entry_shortcuts(self, entry: tk.Entry):
        """
        Добавляет хоткеи Ctrl+A/C/V/X, работающие независимо от раскладки
        (для Windows используем keycode), и контекстное меню по правому клику.
        """

        def on_ctrl_key(event):
            # На Windows keycode для букв стабилен, независимо от раскладки:
            # A/Ф = 65, C/С = 67, X/Ч = 88, V/М = 86
            kc = event.keycode

            # Для Windows делаем привязку по keycode
            if sys.platform.startswith("win"):
                if kc == 65:  # A / Ф
                    entry.selection_range(0, tk.END)
                    entry.icursor(tk.END)
                    return "break"

                if kc == 67:  # C / С
                    entry.event_generate("<<Copy>>")
                    return "break"

                if kc == 88:  # X / Ч
                    entry.event_generate("<<Cut>>")
                    return "break"

                if kc == 86:  # V / М
                    entry.event_generate("<<Paste>>")
                    return "break"

                return None

            # На других платформах оставляем простую привязку по keysym (EN)
            ks = event.keysym
            if ks in ("a", "A"):
                entry.selection_range(0, tk.END)
                entry.icursor(tk.END)
                return "break"

            if ks in ("c", "C"):
                entry.event_generate("<<Copy>>")
                return "break"

            if ks in ("x", "X"):
                entry.event_generate("<<Cut>>")
                return "break"

            if ks in ("v", "V"):
                entry.event_generate("<<Paste>>")
                return "break"

            return None

        # Один обработчик для всех Ctrl+клавиш
        entry.bind("<Control-KeyPress>", on_ctrl_key)

        # Контекстное меню по правому клику
        entry.bind("<Button-3>", lambda e, ent=entry: self._show_entry_context_menu(ent, e))

    # ---------------- titlebar actions ----------------

    def _on_close(self):
        # При закрытии сохраняем настройки (в том числе API ключ)
        try:
            self._persist_settings()
        except Exception:
            pass
        self.destroy()

    def _on_minimize(self):
        self.overrideredirect(False)
        self.iconify()
        self.after(200, lambda: self.overrideredirect(True))

    def _on_toggle_maximize(self):
        try:
            if self.state() == "zoomed":
                self.state("normal")
                self.max_btn.config(text="▢")
            else:
                self.state("zoomed")
                self.max_btn.config(text="▣")
        except Exception:
            pass

    # ---------------- UI ----------------

    def _build_ui(self):
        # кастомный titlebar
        if self._use_custom_titlebar:
            self.titlebar = ttk.Frame(self, style="Titlebar.TFrame")
            self.titlebar.pack(fill=X)

            # Иконка слева от названия (если есть png)
            if getattr(self, "_titlebar_icon_img", None):
                self.title_icon_lbl = ttk.Label(
                    self.titlebar,
                    image=self._titlebar_icon_img,
                    style="Titlebar.TLabel"
                )
                self.title_icon_lbl.pack(side=LEFT, padx=(0, 6))

            self.title_lbl = ttk.Label(self.titlebar, text=self._t("title"), style="Titlebar.TLabel")
            self.title_lbl.pack(side=LEFT)

            ttk.Frame(self.titlebar).pack(side=LEFT, fill=X, expand=True)

            # Порядок справа налево как в Windows: Закрыть, Развернуть, Свернуть
            self.close_btn = ttk.Button(
                self.titlebar, text="X", width=3, style="Titlebar.TButton",
                command=self._on_close
            )
            self.close_btn.pack(side=RIGHT, padx=(2, 0), ipady=2)

            self.max_btn = ttk.Button(
                self.titlebar, text="▢", width=3, style="Titlebar.TButton",
                command=self._on_toggle_maximize
            )
            self.max_btn.pack(side=RIGHT, padx=(2, 0), ipady=2)

            self.min_btn = ttk.Button(
                self.titlebar, text="—", width=3, style="Titlebar.TButton",
                command=self._on_minimize
            )
            self.min_btn.pack(side=RIGHT, padx=(2, 0), ipady=2)

            # Перетаскивание окна мышью
            self._drag_start_x = 0
            self._drag_start_y = 0

            def start_move(e):
                self._drag_start_x = e.x_root
                self._drag_start_y = e.y_root

            def do_move(e):
                dx = e.x_root - self._drag_start_x
                dy = e.y_root - self._drag_start_y
                x = self.winfo_x() + dx
                y = self.winfo_y() + dy
                self.geometry(f"+{x}+{y}")
                self._drag_start_x = e.x_root
                self._drag_start_y = e.y_root

            self.titlebar.bind("<ButtonPress-1>", start_move)
            self.titlebar.bind("<B1-Motion>", do_move)
            self.title_lbl.bind("<ButtonPress-1>", start_move)
            self.title_lbl.bind("<B1-Motion>", do_move)

            if getattr(self, "title_icon_lbl", None):
                self.title_icon_lbl.bind("<ButtonPress-1>", start_move)
                self.title_icon_lbl.bind("<B1-Motion>", do_move)

            self.titlebar.bind("<Double-Button-1>", lambda e: self._on_toggle_maximize())

        # scrollable container
        if ScrolledFrame:
            self.container = ScrolledFrame(self, autohide=True, padding=14)
            self.container.pack(fill=BOTH, expand=True)
        else:
            canvas = tk.Canvas(self, highlightthickness=0)
            scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side=RIGHT, fill=Y)
            canvas.pack(side=LEFT, fill=BOTH, expand=True)

            inner = ttk.Frame(canvas, padding=14)
            canvas.create_window((0, 0), window=inner, anchor="nw")

            def on_configure(_):
                canvas.configure(scrollregion=canvas.bbox("all"))

            inner.bind("<Configure>", on_configure)
            self.container = inner

        # topbar
        topbar = ttk.Frame(self.container, style="Topbar.TFrame")
        topbar.pack(fill=X, pady=(0, 10))

        self.ui_lang_lbl = ttk.Label(topbar, text="", style="Topbar.TLabel")
        self.ui_lang_lbl.pack(side=LEFT)

        self.ui_lang_combo = ttk.Combobox(
            topbar,
            values=["RU", "EN"],
            width=6,
            state="readonly"
        )
        self.ui_lang_combo.pack(side=LEFT, padx=(8, 0))
        self.ui_lang_combo.bind("<<ComboboxSelected>>", self._on_ui_lang_select)
        self.ui_lang_combo.current(0)

        ttk.Separator(self.container).pack(fill=X, pady=(0, 8))

        # file picker
        self.file_frame = ttk.Labelframe(self.container, text="", padding=12)
        self.file_frame.pack(fill=X, pady=(0, 10))

        self.file_entry = ttk.Entry(self.file_frame, textvariable=self.file_path)
        self.file_entry.pack(side=LEFT, fill=X, expand=True)
        self._bind_entry_shortcuts(self.file_entry)

        self.browse_btn = ttk.Button(self.file_frame, text="", command=self.on_browse)
        self.browse_btn.pack(side=LEFT, padx=(8, 0))

        # options
        self.opts = ttk.Labelframe(self.container, text="", padding=12)
        self.opts.pack(fill=X, pady=(0, 10))

        self.summary_cb = ttk.Checkbutton(
            self.opts,
            text="",
            variable=self.summary_var,
            command=self._update_summary_dependent_ui
        )
        self.summary_cb.pack(anchor=W)

        self.api_row = ttk.Frame(self.opts)
        self.api_row.pack(fill=X, pady=(6, 0))

        self.api_key_lbl = ttk.Label(self.api_row, text="")
        self.api_key_lbl.pack(side=LEFT)

        # tk.Entry вместо ttk.Entry, плюс автосохранение при уходе с фокуса
        self.api_key_entry = tk.Entry(
            self.api_row,
            textvariable=self.api_key_var,
            width=42,
            show="*"
        )
        self.api_key_entry.pack(side=LEFT, padx=(6, 0))

        # Автосохранение при уходе с поля
        self.api_key_entry.bind("<FocusOut>", lambda e: self._persist_settings())

        # Шорткаты и контекстное меню (Ctrl+C / Ctrl+V / меню по правому клику)
        self._bind_entry_shortcuts(self.api_key_entry)

        self.api_key_toggle_btn = ttk.Button(
            self.api_row, text="", width=10, command=self.toggle_api_key_visibility
        )
        self.api_key_toggle_btn.pack(side=LEFT, padx=(6, 0))

        self.test_llm_btn = ttk.Button(self.api_row, text="", command=self.on_test_llm)
        self.test_llm_btn.pack(side=LEFT, padx=(8, 0))

        self.summary_format_row = ttk.Frame(self.opts)
        self.summary_format_row.pack(fill=X, pady=(6, 0))

        self.summary_format_lbl = ttk.Label(self.summary_format_row, text="")
        self.summary_format_lbl.pack(side=LEFT)

        self.summary_format_combo = ttk.Combobox(
            self.summary_format_row,
            textvariable=self.summary_format_var,
            values=[],
            width=16,
            state="readonly"
        )
        self.summary_format_combo.pack(side=LEFT, padx=(6, 0))
        self.summary_format_combo.bind("<<ComboboxSelected>>", self._on_format_select)

        self.transcript_cb = ttk.Checkbutton(self.opts, text="", variable=self.transcript_var)
        self.transcript_cb.pack(anchor=W, pady=(8, 0))

        # transcription language
        self.lang_frame = ttk.Frame(self.opts)
        self.lang_frame.pack(fill=X, pady=(10, 0))

        self.lang_lbl = ttk.Label(self.lang_frame, text="")
        self.lang_lbl.pack(side=LEFT)

        self.lang_combo = ttk.Combobox(
            self.lang_frame,
            textvariable=self.lang_var,
            values=[],
            width=10,
            state="readonly"
        )
        self.lang_combo.pack(side=LEFT, padx=(6, 0))
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_transcribe_lang_select)

        # buttons
        btn_frame = ttk.Frame(self.container)
        btn_frame.pack(fill=X, pady=(6, 10))

        self.start_btn = ttk.Button(btn_frame, text="", bootstyle=SUCCESS, command=self.on_start)
        self.start_btn.pack(side=LEFT)

        self.cancel_btn = ttk.Button(btn_frame, text="", bootstyle=DANGER, command=self.on_cancel, state=DISABLED)
        self.cancel_btn.pack(side=LEFT, padx=(8, 0))

        self.open_folder_btn = ttk.Button(btn_frame, text="", command=self.on_open_folder, state=DISABLED)
        self.open_folder_btn.pack(side=LEFT, padx=(8, 0))

        # progress
        self.prog = ttk.Labelframe(self.container, text="", padding=12)
        self.prog.pack(fill=X, pady=(0, 10))

        progress_header = ttk.Frame(self.prog)
        progress_header.pack(fill=X)

        self.progress_header_lbl = ttk.Label(progress_header, text="")
        self.progress_header_lbl.pack(side=LEFT)

        self.progress_info_lbl = ttk.Label(progress_header, text="ⓘ", bootstyle="info")
        self.progress_info_lbl.pack(side=LEFT, padx=(6, 0))
        self.progress_tooltip = ToolTip(self.progress_info_lbl, "")

        self.progress_bar = ttk.Progressbar(self.prog, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=X, pady=(6, 0))

        self.status_lbl = ttk.Label(self.prog, textvariable=self.status_var)
        self.status_lbl.pack(anchor=W, pady=(6, 0))

        # timer
        self.elapsed_row = ttk.Frame(self.prog)
        self.elapsed_row.pack(fill=X, pady=(4, 0))

        self.elapsed_lbl = ttk.Label(self.elapsed_row, text="")
        self.elapsed_lbl.pack(side=LEFT)

        self.elapsed_val_lbl = ttk.Label(self.elapsed_row, textvariable=self.elapsed_var)
        self.elapsed_val_lbl.pack(side=LEFT, padx=(6, 0))

        self.elapsed_row.pack_forget()

        # advanced
        self.adv_visible = tk.BooleanVar(value=False)
        self.adv_toggle = ttk.Checkbutton(
            self.container,
            text="",
            variable=self.adv_visible,
            command=self.toggle_advanced
        )
        self.adv_toggle.pack(anchor=W, pady=(4, 0))

        self.adv_outer = ttk.Labelframe(self.container, text="", padding=12)
        self.adv_frame = self.adv_outer

        row1 = ttk.Frame(self.adv_frame)
        row1.pack(fill=X, pady=2)

        self.whisper_lbl = ttk.Label(row1, text="")
        self.whisper_lbl.pack(side=LEFT)

        ttk.Entry(row1, textvariable=self.whisper_model_var, width=35).pack(side=LEFT, padx=6)

        self.whisper_browse_btn = ttk.Button(row1, text="", command=self.on_browse_whisper_model)
        self.whisper_browse_btn.pack(side=LEFT)

        self.models_open_btn = ttk.Button(row1, text="", command=self.on_open_models_releases)
        self.models_open_btn.pack(side=LEFT, padx=(6, 0))

        self.models_more_lbl = ttk.Label(row1, text="ⓘ", bootstyle="info")
        self.models_more_lbl.pack(side=LEFT, padx=(6, 0))
        self.models_more_tooltip = ToolTip(self.models_more_lbl, "")

        row2 = ttk.Frame(self.adv_frame)
        row2.pack(fill=X, pady=2)

        self.llm_lbl = ttk.Label(row2, text="")
        self.llm_lbl.pack(side=LEFT)
        ttk.Entry(row2, textvariable=self.llm_model_var, width=35).pack(side=LEFT, padx=6)

        row3 = ttk.Frame(self.adv_frame)
        row3.pack(fill=X, pady=2)

        self.max_tokens_lbl = ttk.Label(row3, text="")
        self.max_tokens_lbl.pack(side=LEFT)
        ttk.Spinbox(row3, from_=128, to=4096, textvariable=self.max_tokens_var, width=10).pack(side=LEFT, padx=6)

        row4 = ttk.Frame(self.adv_frame)
        row4.pack(fill=X, pady=2)

        self.prompt_lbl = ttk.Label(row4, text="")
        self.prompt_lbl.pack(side=LEFT)
        ttk.Entry(row4, textvariable=self.prompt_path_var, width=35).pack(side=LEFT, padx=6)

        self.prompt_browse_btn = ttk.Button(row4, text="", command=self.on_browse_prompt)
        self.prompt_browse_btn.pack(side=LEFT)

        self.prompt_edit_btn = ttk.Button(row4, text="", command=self.on_edit_prompt)
        self.prompt_edit_btn.pack(side=LEFT, padx=(6, 0))

        self.chunk_box = ttk.Labelframe(self.adv_frame, text="", padding=10)
        self.chunk_box.pack(fill=X, pady=(8, 0))

        chunk_header = ttk.Frame(self.chunk_box)
        chunk_header.pack(fill=X)

        self.chunk_header_lbl = ttk.Label(chunk_header, text="", font=("Segoe UI", 10, "bold"))
        self.chunk_header_lbl.pack(side=LEFT)

        self.chunk_info_lbl = ttk.Label(chunk_header, text="ⓘ", bootstyle="info")
        self.chunk_info_lbl.pack(side=LEFT, padx=(6, 0))
        self.chunk_tooltip = ToolTip(self.chunk_info_lbl, "")

        r5 = ttk.Frame(self.chunk_box)
        r5.pack(fill=X, pady=2)
        self.threshold_lbl = ttk.Label(r5, text="")
        self.threshold_lbl.pack(side=LEFT)
        ttk.Spinbox(r5, from_=1000, to=30000, textvariable=self.chunk_threshold_var, width=10).pack(side=LEFT, padx=6)

        r6 = ttk.Frame(self.chunk_box)
        r6.pack(fill=X, pady=2)
        self.chunk_size_lbl = ttk.Label(r6, text="")
        self.chunk_size_lbl.pack(side=LEFT)
        ttk.Spinbox(r6, from_=1000, to=10000, textvariable=self.chunk_size_var, width=10).pack(side=LEFT, padx=6)

        r7 = ttk.Frame(self.chunk_box)
        r7.pack(fill=X, pady=2)
        self.overlap_lbl = ttk.Label(r7, text="")
        self.overlap_lbl.pack(side=LEFT)
        ttk.Spinbox(r7, from_=0, to=2000, textvariable=self.chunk_overlap_var, width=10).pack(side=LEFT, padx=6)

        # Sizegrip для ресайза
        if self._use_custom_titlebar:
            self.sizegrip = ttk.Sizegrip(self)
            self.sizegrip.place(relx=1.0, rely=1.0, anchor="se")

    # ---------------- i18n helpers ----------------

    def _t(self, key: str) -> str:
        lang = self.ui_lang_var.get()
        return I18N.get(lang, I18N["en"]).get(key, key)

    def _on_ui_lang_select(self, _=None):
        selected = self.ui_lang_combo.get().strip().upper()
        self.ui_lang_var.set("ru" if selected == "RU" else "en")

        # Авто-синк языка транскрипции с UI, пока пользователь не менял вручную
        if not self._lang_user_overridden:
            self.lang_var.set("ru" if self.ui_lang_var.get() == "ru" else "en")

        self._apply_i18n()

    def _on_transcribe_lang_select(self, _=None):
        raw = self.lang_combo.get().strip().lower()

        if raw.startswith("auto"):
            self.lang_var.set("auto")
        elif raw == "ru":
            self.lang_var.set("ru")
        elif raw == "en":
            self.lang_var.set("en")

        # Пользователь тронул руками - больше не перетираем при смене UI
        self._lang_user_overridden = True

    def _refresh_lang_combo(self):
        auto_label = self._t("lang_auto")
        self.lang_combo["values"] = [auto_label, "RU", "EN"]

        current = (self.lang_var.get() or "auto").lower()
        if current == "auto":
            self.lang_combo.set(auto_label)
        elif current == "ru":
            self.lang_combo.set("RU")
        elif current == "en":
            self.lang_combo.set("EN")
        else:
            ui = self.ui_lang_var.get()
            fallback = "RU" if ui == "ru" else "EN"
            self.lang_combo.set(fallback)
            self.lang_var.set(ui)

    def _refresh_summary_format_combo(self):
        self.summary_format_combo["values"] = [
            self._t("summary_format_md"),
            self._t("summary_format_txt"),
        ]
        if self.summary_format_var.get() == "txt":
            self.summary_format_combo.set(self._t("summary_format_txt"))
        else:
            self.summary_format_combo.set(self._t("summary_format_md"))

    def _apply_i18n(self):
        self.title(self._t("title"))
        if getattr(self, "_use_custom_titlebar", False):
            self.title_lbl.config(text=self._t("title"))

        self.ui_lang_lbl.config(text=self._t("ui_lang"))
        self.file_frame.config(text=self._t("input_file"))
        self.browse_btn.config(text=self._t("browse"))

        self.opts.config(text=self._t("output"))
        self.summary_cb.config(text=self._t("gen_summary"))
        self.transcript_cb.config(text=self._t("save_transcript"))
        self.summary_format_lbl.config(text=self._t("summary_format"))
        self.api_key_lbl.config(text=self._t("api_key"))
        self.lang_lbl.config(text=self._t("language"))

        self.test_llm_btn.config(text=self._t("test_llm"))
        self._update_api_toggle_label()

        self.start_btn.config(text=self._t("start"))
        self.cancel_btn.config(text=self._t("cancel"))
        self.open_folder_btn.config(text=self._t("open_folder"))

        self.prog.config(text=self._t("progress"))
        self.progress_header_lbl.config(text=self._t("progress"))
        self.progress_tooltip.text = self._t("progress_help")

        self.elapsed_lbl.config(text=self._t("elapsed"))

        self.adv_toggle.config(text=self._t("advanced_toggle"))
        self.adv_outer.config(text=self._t("advanced"))

        self.whisper_lbl.config(text=self._t("whisper_model"))
        self.whisper_browse_btn.config(text=self._t("whisper_browse"))
        self.models_open_btn.config(text=self._t("models_open"))
        self.models_more_tooltip.text = self._t("models_help")

        self.llm_lbl.config(text=self._t("llm_model"))
        self.max_tokens_lbl.config(text=self._t("max_tokens"))
        self.prompt_lbl.config(text=self._t("prompt_file"))
        self.prompt_browse_btn.config(text=self._t("browse"))
        self.prompt_edit_btn.config(text=self._t("prompt_edit"))

        self.chunk_box.config(text=self._t("chunking"))
        self.chunk_header_lbl.config(text=self._t("chunking"))
        self.chunk_tooltip.text = self._t("chunk_help")
        self.threshold_lbl.config(text=self._t("threshold_words"))
        self.chunk_size_lbl.config(text=self._t("chunk_size_words"))
        self.overlap_lbl.config(text=self._t("overlap_words"))

        self._refresh_summary_format_combo()
        self._refresh_lang_combo()

        self.ui_lang_combo.set("RU" if self.ui_lang_var.get() == "ru" else "EN")

        if not self.is_running:
            self.status_var.set(self._t("status_idle"))

    # ---------------- summary-dependent visibility ----------------

    def _update_summary_dependent_ui(self):
        if self.summary_var.get():
            if not self.api_row.winfo_ismapped():
                self.api_row.pack(fill=X, pady=(6, 0), before=self.transcript_cb)
            if not self.summary_format_row.winfo_ismapped():
                self.summary_format_row.pack(fill=X, pady=(6, 0), before=self.transcript_cb)
        else:
            self.api_row.pack_forget()
            self.summary_format_row.pack_forget()

    # ---------------- callbacks ----------------

    def _on_format_select(self, _=None):
        raw = self.summary_format_combo.get().lower()
        self.summary_format_var.set("txt" if "txt" in raw else "md")

    def toggle_api_key_visibility(self):
        self.api_key_visible = not self.api_key_visible
        self.api_key_entry.config(show="" if self.api_key_visible else "*")
        self._update_api_toggle_label()

    def _update_api_toggle_label(self):
        text_key = "hide_api_key" if self.api_key_visible else "show_api_key"
        self.api_key_toggle_btn.config(text=self._t(text_key))

    def toggle_advanced(self):
        if self.adv_visible.get():
            self.adv_outer.pack(fill=X, pady=(6, 0))
        else:
            self.adv_outer.pack_forget()

    def on_browse(self):
        path = filedialog.askopenfilename(
            title="Select media file",
            filetypes=[
                ("Media files", "*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.flac *.m4a *.ogg *.opus"),
                ("All files", "*.*")
            ]
        )
        if path:
            self.file_path.set(path)
            self.open_folder_btn.config(state=DISABLED)

    def on_browse_whisper_model(self):
        models_dir = (PROJECT_ROOT / "models")
        path = filedialog.askopenfilename(
            title="Select Whisper model",
            initialdir=str(models_dir) if models_dir.exists() else None,
            filetypes=[("Whisper models", "*.bin"), ("All files", "*.*")]
        )
        if path:
            p = Path(path).resolve()
            try:
                rel = p.relative_to(PROJECT_ROOT)
                self.whisper_model_var.set(str(rel).replace("\\", "/"))
            except Exception:
                self.whisper_model_var.set(str(p))

    def on_open_models_releases(self):
        webbrowser.open("https://github.com/ggerganov/whisper.cpp/releases")

    def on_browse_prompt(self):
        path = filedialog.askopenfilename(
            title="Select prompt file",
            filetypes=[("Text files", "*.txt *.md"), ("All files", "*.*")]
        )
        if path:
            p = Path(path).resolve()
            try:
                rel = p.relative_to(PROJECT_ROOT)
                self.prompt_path_var.set(str(rel).replace("\\", "/"))
            except Exception:
                self.prompt_path_var.set(str(p))

    def on_edit_prompt(self):
        prompt_path = Path(self.prompt_path_var.get()).expanduser()
        if not prompt_path.is_file():
            candidate = PROJECT_ROOT / prompt_path
            if candidate.is_file():
                prompt_path = candidate
            else:
                messagebox.showwarning(self._t("error_title"), f"Prompt file not found:\n{prompt_path}")
                return

        try:
            if sys.platform.startswith("win"):
                os.startfile(str(prompt_path))
            elif sys.platform.startswith("darwin"):
                subprocess.run(["open", str(prompt_path)])
            else:
                subprocess.run(["xdg-open", str(prompt_path)])
        except Exception as e:
            messagebox.showerror(self._t("error_title"), f"Cannot open file:\n{e}")

    def on_open_folder(self):
        if not self.file_path.get():
            return
        folder = str(Path(self.file_path.get()).resolve().parent)
        try:
            os.startfile(folder)
        except Exception:
            pass

    def on_cancel(self):
        self.cancel_event.set()
        self.status_var.set(self._t("cancelled"))
        self._stop_progress_pulse()
        self._stop_pseudo_progress()
        self.cancel_btn.config(state=DISABLED)
        self.is_running = False
        self._stop_timer()
        self.elapsed_row.pack_forget()

    def on_test_llm(self):
        # Перед тестом сохраняем текущие настройки
        try:
            self._persist_settings()
        except Exception:
            pass

        api_key = self.api_key_var.get().strip()
        model = self.llm_model_var.get().strip() or "openai/gpt-4.1-mini"

        if not api_key:
            messagebox.showwarning(self._t("error_title"), "API key is empty.")
            return

        self.test_llm_btn.config(state=DISABLED)
        self.status_var.set(self._t("status_testing_llm"))

        def worker():
            try:                
                from src.summarizer import call_openrouter_chat

                ui_lang = self.ui_lang_var.get()
                if ui_lang == "ru":
                    prompt = (
                        "Короткий тест доступности.\n"
                        "Ответь на русском в 3-5 строк:\n"
                        "1) Укажи точный id модели, от имени которой отвечаешь.\n"
                        "2) Подтверди, что ключ работает и есть доступ к API.\n"
                        "3) Коротко скажи, что у тебя нет доступа к биллингу и личным данным, если это так.\n"
                        "Будь кратким."
                    )
                else:
                    prompt = (
                        "This is a short connectivity test.\n"
                        "Reply in English in 3-5 short lines:\n"
                        "1) The exact model id you are answering as.\n"
                        "2) Confirm that the API key works and you can reply.\n"
                        "3) Briefly state that you do NOT have access to private key or billing details.\n"
                        "Keep it concise."
                    )

                reply = call_openrouter_chat(
                    api_key=api_key,
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a diagnostic endpoint."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=80,
                    temperature=0,
                )

                self.after(0, lambda: messagebox.showinfo(self._t("done_title"), reply))

            except Exception as e:
                err = str(e)
                self.after(0, lambda: messagebox.showerror(
                    self._t("error_title"),
                    self._t("test_llm_fail").format(error=err)
                ))
            finally:
                self.after(0, lambda: self.test_llm_btn.config(state=NORMAL))
                self.after(0, lambda: self.status_var.set(self._t("status_idle")))

        threading.Thread(target=worker, daemon=True).start()


    def on_start(self):
        media = self.file_path.get().strip()
        if not media:
            messagebox.showwarning("No file", self._t("no_file"))
            return

        if not self.summary_var.get() and not self.transcript_var.get():
            messagebox.showwarning("No output", self._t("no_output"))
            return

        # Сохраняем настройки (включая текущий API ключ) перед запуском пайплайна
        self._persist_settings()

        self.cancel_event.clear()
        self.is_running = True
        self.start_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.open_folder_btn.config(state=DISABLED)
        self.status_var.set(self._t("status_starting"))
        self.progress_var.set(0)
        self._stop_progress_pulse()
        self._stop_pseudo_progress()

        self._start_timer()
        self.elapsed_row.pack(fill=X, pady=(4, 0))

        def progress_cb(stage: str, percent: int, message: str):
            self._last_stage = stage
            self.after(0, lambda: self._update_progress(percent, message or stage))

        reporter = ProgressReporter(progress_cb)

        def worker():
            try:                
                from src.pipeline import process_video, ProcessingError

                lang = None if self.lang_var.get() == "auto" else self.lang_var.get()

                result_path = process_video(
                    video_path=Path(media),
                    language=lang,
                    keep_temp=False,
                    summary_only=self.summary_var.get(),
                    with_transcript=self.transcript_var.get(),
                    progress=reporter,
                    cancel_event=self.cancel_event,
                    summary_format=self.summary_format_var.get(),
                )

                self.after(0, lambda rp=result_path: self._on_done(rp))

            except ProcessingError as e:
                msg = str(e)
                self.after(0, lambda m=msg: self._on_error(m))
            except Exception as e:
                msg = f"Unexpected error: {e}\n{traceback.format_exc()}"
                self.after(0, lambda m=msg: self._on_error(m))


        threading.Thread(target=worker, daemon=True).start()

    # ---------------- progress + timer ----------------

    def _update_progress(self, percent: int, message: str):
        if percent < 0:
            if not self.progress_indeterminate:
                self.progress_bar.start(10)
                self.progress_indeterminate = True
            if self._last_stage:
                self._start_pseudo_progress(self._last_stage)
            self.status_var.set(message)
            return

        if self.progress_indeterminate:
            self.progress_bar.stop()
            self.progress_indeterminate = False

        self._stop_pseudo_progress()
        self.progress_var.set(max(0, min(100, percent)))
        self.status_var.set(message)

    def _start_pseudo_progress(self, stage: str):
        rng = self.stage_ranges.get(stage)
        if not rng:
            return
        start, end = rng
        self._pseudo_target_to = end
        if self.progress_var.get() < start:
            self.progress_var.set(start)
        self._schedule_pseudo_tick()

    def _schedule_pseudo_tick(self):
        if not self.progress_indeterminate or self._pseudo_target_to is None:
            return
        current = self.progress_var.get()
        target = self._pseudo_target_to
        if current < target:
            self.progress_var.set(current + 1)
            self._pseudo_job = self.after(250, self._schedule_pseudo_tick)

    def _stop_pseudo_progress(self):
        if self._pseudo_job is not None:
            try:
                self.after_cancel(self._pseudo_job)
            except Exception:
                pass
        self._pseudo_job = None
        self._pseudo_target_to = None

    def _start_timer(self):
        self.start_time = time.time()
        self.elapsed_var.set("00:00")
        self._schedule_timer_tick()

    def _schedule_timer_tick(self):
        if not self.is_running or self.start_time is None:
            return
        elapsed = int(time.time() - self.start_time)
        mins = elapsed // 60
        secs = elapsed % 60
        self.elapsed_var.set(f"{mins:02d}:{secs:02d}")
        self._timer_job = self.after(1000, self._schedule_timer_tick)

    def _stop_timer(self):
        if self._timer_job is not None:
            try:
                self.after_cancel(self._timer_job)
            except Exception:
                pass
        self._timer_job = None
        self.start_time = None

    def _stop_progress_pulse(self):
        if self.progress_indeterminate:
            self.progress_bar.stop()
            self.progress_indeterminate = False

    # ---------------- done/error ----------------

    def _on_done(self, result_path: Path):
        self.start_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)
        self.open_folder_btn.config(state=NORMAL)
        self.is_running = False
        self.status_var.set(f"{self._t('status_done_prefix')}: {result_path.name}")
        self.progress_var.set(100)
        self._stop_progress_pulse()
        self._stop_pseudo_progress()
        self._stop_timer()
        self.elapsed_row.pack_forget()
        messagebox.showinfo(self._t("done_title"), self._t("done_msg").format(path=result_path))

    def _on_error(self, msg: str):
        self.start_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)
        self.open_folder_btn.config(state=DISABLED)
        self.is_running = False
        self.status_var.set(self._t("status_error"))
        self._stop_progress_pulse()
        self._stop_pseudo_progress()
        self._stop_timer()
        self.elapsed_row.pack_forget()
        messagebox.showerror(self._t("error_title"), msg)

    # ---------------- settings persistence ----------------

    def _persist_settings(self):
        import json
        local_path, user_path = ensure_local_settings_files()

        user_overrides = {"openrouter_api_key": self.api_key_var.get().strip()}
        user_path.write_text(
            json.dumps(user_overrides, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        self.settings["summary_format"] = self.summary_format_var.get().strip()
        self.settings["whisper_model"] = self.whisper_model_var.get().strip()
        self.settings["openrouter_model"] = self.llm_model_var.get().strip()
        self.settings["summary_max_tokens"] = int(self.max_tokens_var.get())
        self.settings["summary_prompt"] = self.prompt_path_var.get().strip()

        self.settings["chunk_threshold_words"] = int(self.chunk_threshold_var.get())
        self.settings["chunk_max_words"] = int(self.chunk_size_var.get())
        self.settings["chunk_overlap_words"] = int(self.chunk_overlap_var.get())

        local_path.write_text(
            json.dumps(self.settings, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


def main():
    app = MeetingNotesGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
