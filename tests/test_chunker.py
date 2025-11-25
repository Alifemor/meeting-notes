# tests/test_chunker.py
from src.chunker import split_text_into_chunks

def test_split_text_no_chunking():
    text = "word " * 100
    chunks = split_text_into_chunks(text, max_words=500)
    assert len(chunks) == 1

def test_split_text_chunking_with_overlap():
    text = "word " * 1200
    chunks = split_text_into_chunks(text, max_words=500, overlap_words=50)

    assert len(chunks) >= 2
    # Проверяем, что чанки не пустые
    assert all(len(c.split()) > 0 for c in chunks)
    # Проверяем перекрытие: начало второго чанка содержит хвост первого
    c1_last = chunks[0].split()[-50:]
    c2_first = chunks[1].split()[:50]
    assert c1_last == c2_first
