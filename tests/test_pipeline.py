from pathlib import Path
import tempfile

from src.pipeline import process_video


def _fake_settings(model_path: Path, summary_format="md"):
    return {
        "ffmpeg_path": "ffmpeg",
        "whisper_path": "whisper",
        "whisper_model": str(model_path),
        "temp_dir": None,

        "openrouter_api_key": "x",
        "openrouter_model": "openai/gpt-4.1-mini",
        "summary_max_tokens": 1024,
        "summary_prompt": None,

        "chunk_threshold_words": 4000,
        "chunk_max_words": 3500,
        "chunk_overlap_words": 200,

        "summary_format": summary_format,  # важно для тестов
    }


def test_pipeline_transcript_only_audio(monkeypatch):
    def fake_transcribe_audio(audio_path, whisper_path, model_path, language, output_dir, cancel_event=None):
        tmp = Path(output_dir) / "fake_transcript.txt"
        tmp.write_text("hello world", encoding="utf-8")
        return tmp

    monkeypatch.setattr("src.pipeline.transcribe_audio", fake_transcribe_audio)
    monkeypatch.setattr("src.pipeline.is_audio_file", lambda p: True)

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)

        # фейковая модель, чтобы пройти model_path.is_file()
        model = d / "ggml-fake.bin"
        model.write_text("dummy", encoding="utf-8")

        monkeypatch.setattr("src.pipeline.load_settings", lambda: _fake_settings(model))

        audio = d / "test.mp3"
        audio.write_text("dummy", encoding="utf-8")

        result = process_video(audio, summary_only=False, keep_temp=True)

        assert result.is_file()
        assert result.name == "test_transcript.txt"
        assert "hello world" in result.read_text(encoding="utf-8")


def test_pipeline_summary_only_short(monkeypatch):
    def fake_transcribe_audio(audio_path, whisper_path, model_path, language, output_dir, cancel_event=None):
        tmp = Path(output_dir) / "fake_transcript.txt"
        tmp.write_text("word " * 1000, encoding="utf-8")
        return tmp

    def fake_summary(**kwargs):
        return "# Summary\n\nOK"

    monkeypatch.setattr("src.pipeline.transcribe_audio", fake_transcribe_audio)
    monkeypatch.setattr("src.pipeline.is_audio_file", lambda p: True)
    monkeypatch.setattr("src.pipeline.generate_llm_summary_markdown", fake_summary)

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        model = d / "ggml-fake.bin"
        model.write_text("dummy", encoding="utf-8")

        monkeypatch.setattr("src.pipeline.load_settings", lambda: _fake_settings(model, summary_format="md"))

        audio = d / "test.mp3"
        audio.write_text("dummy", encoding="utf-8")

        result = process_video(audio, summary_only=True, with_transcript=False, keep_temp=True)

        assert result.is_file()
        assert result.name == "test_summary.md"
        assert "OK" in result.read_text(encoding="utf-8")


def test_pipeline_summary_only_long_uses_chunking(monkeypatch):
    called = {"chunking": False}

    def fake_transcribe_audio(audio_path, whisper_path, model_path, language, output_dir, cancel_event=None):
        tmp = Path(output_dir) / "fake_transcript.txt"
        tmp.write_text("word " * 10000, encoding="utf-8")
        return tmp

    def fake_chunking(**kwargs):
        called["chunking"] = True
        return "# Summary\n\nCHUNKED"

    monkeypatch.setattr("src.pipeline.transcribe_audio", fake_transcribe_audio)
    monkeypatch.setattr("src.pipeline.is_audio_file", lambda p: True)
    monkeypatch.setattr("src.pipeline.summarize_transcript_with_chunking", fake_chunking)

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        model = d / "ggml-fake.bin"
        model.write_text("dummy", encoding="utf-8")

        monkeypatch.setattr("src.pipeline.load_settings", lambda: _fake_settings(model, summary_format="md"))

        audio = d / "test.mp3"
        audio.write_text("dummy", encoding="utf-8")

        result = process_video(audio, summary_only=True, keep_temp=True)

        assert called["chunking"] is True
        assert result.suffix == ".md"
        assert "CHUNKED" in result.read_text(encoding="utf-8")
