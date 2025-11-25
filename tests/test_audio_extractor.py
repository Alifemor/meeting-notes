# tests/test_audio_extractor.py
from pathlib import Path
from src.audio_extractor import is_audio_file

def test_is_audio_file_true():
    assert is_audio_file(Path("a.mp3"))
    assert is_audio_file(Path("b.WAV"))
    assert is_audio_file(Path("c.m4a"))

def test_is_audio_file_false():
    assert not is_audio_file(Path("a.mp4"))
    assert not is_audio_file(Path("b.mkv"))
    assert not is_audio_file(Path("c.txt"))