from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List

import pytest

from biblicus.corpus import Corpus
from biblicus.context_engine import ContextRetrieverRequest
from tactus.core import retrieval


class DummyColumn:
    def __init__(self, values: List[str]):
        self._values = values

    def to_pylist(self) -> List[str]:
        return self._values


class DummyTable:
    def __init__(self, values: List[str]):
        self._values = values

    def column(self, _name: str) -> DummyColumn:
        return DummyColumn(self._values)


def test_get_wikitext2_cache_dir_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TACTUS_WIKITEXT2_CACHE_DIR", str(tmp_path))
    assert retrieval.get_wikitext2_cache_dir() == tmp_path


def test_get_wikitext2_cache_dir_default(monkeypatch):
    monkeypatch.delenv("TACTUS_WIKITEXT2_CACHE_DIR", raising=False)
    cache_dir = retrieval.get_wikitext2_cache_dir()
    assert "tests/fixtures/wikitext-2-raw-v1" in str(cache_dir)


def test_get_noaa_afd_cache_dir_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TACTUS_NOAA_AFD_DIR", str(tmp_path))
    assert retrieval.get_noaa_afd_cache_dir() == tmp_path


def test_get_noaa_afd_cache_dir_default(monkeypatch):
    monkeypatch.delenv("TACTUS_NOAA_AFD_DIR", raising=False)
    cache_dir = retrieval.get_noaa_afd_cache_dir()
    assert "tests/fixtures/noaa_afd" in str(cache_dir)


def test_load_wikitext2_texts_invalid_split():
    with pytest.raises(ValueError):
        retrieval.load_wikitext2_texts(split="unknown")


def test_load_wikitext2_texts_limit(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(retrieval, "ensure_wikitext2_raw", lambda: tmp_path)

    def fake_read_table(_path, columns):
        assert columns == ["text"]
        return DummyTable(["one", "two", "three"])

    monkeypatch.setattr(retrieval.pq, "read_table", fake_read_table)
    assert retrieval.load_wikitext2_texts(split="train", limit=2) == ["one", "two"]


def test_load_noaa_afd_texts_missing_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(retrieval, "get_noaa_afd_cache_dir", lambda: tmp_path)
    with pytest.raises(FileNotFoundError):
        retrieval.load_noaa_afd_texts(wfo="MFL")


def test_load_noaa_afd_texts_limit(monkeypatch, tmp_path: Path):
    base = tmp_path / "MFL"
    base.mkdir(parents=True)
    (base / "a.txt").write_text("a")
    (base / "b.txt").write_text("b")
    monkeypatch.setattr(retrieval, "get_noaa_afd_cache_dir", lambda: tmp_path)
    assert retrieval.load_noaa_afd_texts("MFL", limit=1) == ["a"]


def test_load_noaa_afd_texts_no_limit(monkeypatch, tmp_path: Path):
    base = tmp_path / "MFL"
    base.mkdir(parents=True)
    (base / "a.txt").write_text("a")
    (base / "b.txt").write_text("b")
    monkeypatch.setattr(retrieval, "get_noaa_afd_cache_dir", lambda: tmp_path)
    assert retrieval.load_noaa_afd_texts("MFL") == ["a", "b"]


def test_ensure_wikitext2_raw_downloads_when_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        retrieval, "_WIKITEXT2_FILES", {"train": {"filename": "file.parquet", "sha256": "ok"}}
    )
    monkeypatch.setattr(retrieval, "get_wikitext2_cache_dir", lambda: tmp_path)

    def fake_download(_url, target):
        target.write_text("data")

    monkeypatch.setattr(retrieval, "_download_file", fake_download)
    monkeypatch.setattr(retrieval, "_sha256_matches", lambda _path, _sha: True)

    assert retrieval.ensure_wikitext2_raw() == tmp_path


def test_ensure_wikitext2_raw_raises_on_checksum(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        retrieval, "_WIKITEXT2_FILES", {"train": {"filename": "file.parquet", "sha256": "bad"}}
    )
    monkeypatch.setattr(retrieval, "get_wikitext2_cache_dir", lambda: tmp_path)

    def fake_download(_url, target):
        target.write_text("data")

    monkeypatch.setattr(retrieval, "_download_file", fake_download)
    monkeypatch.setattr(retrieval, "_sha256_matches", lambda _path, _sha: False)

    with pytest.raises(RuntimeError):
        retrieval.ensure_wikitext2_raw()


def test_rank_texts_handles_empty_query():
    texts = ["alpha", "beta"]
    assert retrieval._rank_texts("", texts) == texts


def test_rank_texts_no_matches_returns_all():
    texts = ["alpha", "beta"]
    ranked = retrieval._rank_texts("gamma", texts)
    assert ranked == texts


def test_retrieve_wikitext2_truncates(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_wikitext2_texts",
        lambda **_kwargs: ["abcd" * 10, "short"],
    )
    request = ContextRetrieverRequest(
        query="abcd",
        limit=1,
        maximum_total_characters=10,
        metadata={"split": "train"},
    )
    result = retrieval.retrieve_wikitext2(request)
    assert result.text.endswith("...")
    assert len(result.text) <= 10


def test_retrieve_wikitext2_cache_item_limit(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_wikitext2_texts",
        lambda **_kwargs: ["alpha", "beta", "gamma"],
    )
    request = ContextRetrieverRequest(
        query="alpha",
        limit=5,
        maximum_total_characters=100,
        metadata={"split": "train", "maximum_cache_total_items": 1},
    )
    result = retrieval.retrieve_wikitext2(request)
    assert result.evidence_count == 1
    assert "alpha" in result.text


def test_retrieve_wikitext2_cache_character_limit(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_wikitext2_texts",
        lambda **_kwargs: ["alpha", "beta", "gamma"],
    )
    request = ContextRetrieverRequest(
        query="alpha",
        limit=5,
        maximum_total_characters=100,
        metadata={"split": "train", "maximum_cache_total_characters": 8},
    )
    result = retrieval.retrieve_wikitext2(request)
    assert result.evidence_count == 1
    assert result.text.strip() == "alpha"


def test_retrieve_wikitext2_skips_empty_snippets(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_wikitext2_texts",
        lambda **_kwargs: ["   ", "alpha"],
    )
    request = ContextRetrieverRequest(
        query="alpha",
        limit=2,
        maximum_total_characters=100,
        metadata={"split": "train"},
    )
    result = retrieval.retrieve_wikitext2(request)
    assert result.evidence_count == 1


def test_retrieve_wikitext2_skips_empty_snippets_on_no_match(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_wikitext2_texts",
        lambda **_kwargs: ["   ", "alpha"],
    )
    request = ContextRetrieverRequest(
        query="gamma",
        limit=2,
        maximum_total_characters=100,
        metadata={"split": "train"},
    )
    result = retrieval.retrieve_wikitext2(request)
    assert result.evidence_count == 1


def test_retrieve_wikitext2_cache_character_limit_breaks(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_wikitext2_texts",
        lambda **_kwargs: ["alpha", "beta", "gamma"],
    )
    request = ContextRetrieverRequest(
        query="alpha",
        limit=5,
        maximum_total_characters=100,
        metadata={"split": "train", "maximum_cache_total_characters": 6},
    )
    result = retrieval.retrieve_wikitext2(request)
    assert result.evidence_count == 1
    assert result.text.strip() == "alpha"


def test_retrieve_wikitext2_cache_character_limit_skips_all(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_wikitext2_texts",
        lambda **_kwargs: ["alpha", "beta"],
    )
    request = ContextRetrieverRequest(
        query="alpha",
        limit=5,
        maximum_total_characters=100,
        metadata={"split": "train", "maximum_cache_total_characters": 2},
    )
    result = retrieval.retrieve_wikitext2(request)
    assert result.evidence_count == 0


def test_retrieve_wikitext2_updates_remaining_chars(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_wikitext2_texts",
        lambda **_kwargs: ["alpha", "beta"],
    )
    request = ContextRetrieverRequest(
        query="alpha",
        limit=1,
        maximum_total_characters=20,
        metadata={"split": "train"},
    )
    result = retrieval.retrieve_wikitext2(request)
    assert result.evidence_count == 1


def test_retrieve_wikitext2_cache_character_limit_allows_all(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_wikitext2_texts",
        lambda **_kwargs: ["alpha", "beta"],
    )
    request = ContextRetrieverRequest(
        query="gamma",
        limit=5,
        maximum_total_characters=100,
        metadata={"split": "train", "maximum_cache_total_characters": 1000},
    )
    result = retrieval.retrieve_wikitext2(request)
    assert result.evidence_count == 2


def test_retrieve_wikitext2_without_total_character_budget(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_wikitext2_texts",
        lambda **_kwargs: ["alpha"],
    )
    request = ContextRetrieverRequest(
        query="alpha",
        limit=1,
        metadata={"split": "train"},
    )
    result = retrieval.retrieve_wikitext2(request)
    assert result.evidence_count == 1


def test_retrieve_wikitext2_cache_character_limit_breaks_with_no_match(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_wikitext2_texts",
        lambda **_kwargs: ["alpha", "beta"],
    )
    request = ContextRetrieverRequest(
        query="gamma",
        limit=5,
        maximum_total_characters=100,
        metadata={"split": "train", "maximum_cache_total_characters": 6},
    )
    result = retrieval.retrieve_wikitext2(request)
    assert result.evidence_count == 1


def test_retrieve_noaa_afd_cache_item_limit(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["storm", "sun", "wind"],
    )
    request = ContextRetrieverRequest(
        query="storm",
        limit=5,
        maximum_total_characters=100,
        metadata={"wfo": "MFL", "maximum_cache_total_items": 1},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.evidence_count == 1
    assert "storm" in result.text


def test_retrieve_noaa_afd_cache_character_limit(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["storm", "sun", "wind"],
    )
    request = ContextRetrieverRequest(
        query="storm",
        limit=5,
        maximum_total_characters=100,
        metadata={"wfo": "MFL", "maximum_cache_total_characters": 8},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.evidence_count == 1
    assert result.text.strip() == "storm"


def test_retrieve_noaa_afd_cache_character_limit_skips_all(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["storm", "sun"],
    )
    request = ContextRetrieverRequest(
        query="storm",
        limit=5,
        maximum_total_characters=100,
        metadata={"wfo": "MFL", "maximum_cache_total_characters": 2},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.evidence_count == 0


def test_retrieve_noaa_afd_updates_remaining_chars(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["storm", "sun"],
    )
    request = ContextRetrieverRequest(
        query="storm",
        limit=1,
        maximum_total_characters=20,
        metadata={"wfo": "MFL"},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.evidence_count == 1


def test_retrieve_noaa_afd_cache_character_limit_allows_all(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["storm", "sun"],
    )
    request = ContextRetrieverRequest(
        query="gamma",
        limit=5,
        maximum_total_characters=100,
        metadata={"wfo": "MFL", "maximum_cache_total_characters": 1000},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.evidence_count == 2


def test_retrieve_noaa_afd_without_total_character_budget(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["storm"],
    )
    request = ContextRetrieverRequest(
        query="storm",
        limit=1,
        metadata={"wfo": "MFL"},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.evidence_count == 1


def test_retrieve_noaa_afd_truncates_with_remaining_chars(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["stormstorm"],
    )
    request = ContextRetrieverRequest(
        query="storm",
        limit=1,
        maximum_total_characters=5,
        metadata={"wfo": "MFL"},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.text.endswith("...")


def test_retrieve_noaa_afd_breaks_when_budget_reached(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["storm", "sun"],
    )
    request = ContextRetrieverRequest(
        query="storm",
        limit=2,
        maximum_total_characters=5,
        metadata={"wfo": "MFL"},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.evidence_count == 1


def test_retrieve_noaa_afd_breaks_when_remaining_chars_zero(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["a", "b"],
    )
    monkeypatch.setattr(retrieval, "_rank_texts", lambda _query, texts: texts)
    request = ContextRetrieverRequest(
        query="storm",
        limit=2,
        maximum_total_characters=1,
        metadata={"wfo": "MFL"},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.evidence_count == 1
    assert result.blocks[0].text == "a"


def test_retrieve_noaa_afd_skips_empty_snippets_on_no_match(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["   ", "storm"],
    )
    request = ContextRetrieverRequest(
        query="gamma",
        limit=2,
        maximum_total_characters=100,
        metadata={"wfo": "MFL"},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.evidence_count == 1


def test_retrieve_noaa_afd_truncates(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["storm " * 5, "sun"],
    )
    request = ContextRetrieverRequest(
        query="storm",
        limit=1,
        maximum_total_characters=10,
        metadata={"wfo": "MFL"},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.text.endswith("...")


def test_make_retriever_router_prefers_registry_retriever(monkeypatch):
    class DummyRetriever:
        def __init__(self):
            self.config = {"retriever_id": "wikitext2"}

    router = retrieval.make_retriever_router({}, {"search": DummyRetriever()})
    monkeypatch.setattr(retrieval, "retrieve_wikitext2", lambda _req: "ok")
    request = ContextRetrieverRequest(
        query="alpha",
        limit=1,
        maximum_total_characters=10,
        metadata={"retriever": "search"},
    )
    assert router(request) == "ok"


def test_make_retriever_router_uses_registry_retriever_override(monkeypatch):
    class DummyRetriever:
        def __init__(self):
            self.config = {"retriever_id": "noaa_afd"}

    router = retrieval.make_retriever_router({}, {"search": DummyRetriever()})
    monkeypatch.setattr(retrieval, "retrieve_wikitext2", lambda _req: "ok")
    request = ContextRetrieverRequest(
        query="alpha",
        limit=1,
        maximum_total_characters=10,
        metadata={"retriever": "search", "retriever_id": "wikitext2"},
    )
    assert router(request) == "ok"


def test_make_retriever_router_ignores_non_dict_retriever_config(monkeypatch):
    class DummyRetriever:
        def __init__(self):
            self.config = ["retriever_id", "noaa_afd"]

    router = retrieval.make_retriever_router({}, {"search": DummyRetriever()})
    monkeypatch.setattr(retrieval, "retrieve_wikitext2", lambda _req: "ok")
    request = ContextRetrieverRequest(
        query="alpha",
        limit=1,
        maximum_total_characters=10,
        metadata={"retriever": "search", "retriever_id": "wikitext2"},
    )
    assert router(request) == "ok"


def test_make_retriever_router_missing_retriever_id():
    router = retrieval.make_retriever_router({}, {})
    request = ContextRetrieverRequest(
        query="alpha",
        limit=1,
        maximum_total_characters=10,
        metadata={"retriever": "docs"},
    )
    with pytest.raises(ValueError):
        router(request)


def test_make_retriever_router_missing_retriever_id_with_non_dict_config():
    class DummyRetriever:
        def __init__(self):
            self.config = ["retriever_id", "noaa_afd"]

    router = retrieval.make_retriever_router({}, {"search": DummyRetriever()})
    request = ContextRetrieverRequest(
        query="alpha",
        limit=1,
        maximum_total_characters=10,
        metadata={"retriever": "search"},
    )
    with pytest.raises(ValueError):
        router(request)


def test_retrieve_noaa_afd_skips_empty_snippets(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["   ", "storm"],
    )
    request = ContextRetrieverRequest(
        query="storm",
        limit=2,
        maximum_total_characters=100,
        metadata={"wfo": "MFL"},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.evidence_count == 1


def test_retrieve_noaa_afd_stops_when_remaining_zero(monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "load_noaa_afd_texts",
        lambda **_kwargs: ["a", "b"],
    )
    request = ContextRetrieverRequest(
        query="a",
        limit=2,
        maximum_total_characters=1,
        metadata={"wfo": "MFL"},
    )
    result = retrieval.retrieve_noaa_afd(request)
    assert result.evidence_count == 1


def test_retrieve_biblicus_context_pack_requires_retriever_id():
    request = ContextRetrieverRequest(query="cats", limit=1, metadata={"corpus_root": "/tmp"})
    with pytest.raises(ValueError):
        retrieval.retrieve_biblicus_context_pack(request)


def test_retrieve_biblicus_context_pack_requires_corpus_root():
    request = ContextRetrieverRequest(query="cats", limit=1, metadata={"retriever_id": "tf"})
    with pytest.raises(ValueError):
        retrieval.retrieve_biblicus_context_pack(request)


def test_make_retriever_router_resolves_retriever(monkeypatch):
    request = ContextRetrieverRequest(query="alpha", limit=1, metadata={"retriever_id": "noaa_afd"})
    router = retrieval.make_retriever_router({}, {})
    monkeypatch.setattr(retrieval, "retrieve_noaa_afd", lambda _req: "noaa")
    assert router(request) == "noaa"


def test_make_retriever_router_uses_retriever_registry_fallback(monkeypatch):
    class DummySpec:
        def __init__(self):
            self.config = {"retriever_id": "wikitext2"}

    router = retrieval.make_retriever_router({}, {"search": DummySpec()})
    monkeypatch.setattr(retrieval, "retrieve_wikitext2", lambda _req: "wiki")
    request = ContextRetrieverRequest(query="alpha", limit=1, metadata={"retriever": "search"})
    assert router(request) == "wiki"


def test_make_retriever_router_uses_retriever_type_fallback(monkeypatch):
    class DummySpec:
        def __init__(self):
            self.config = {"retriever_type": "wikitext2"}

    router = retrieval.make_retriever_router({}, {"search": DummySpec()})
    monkeypatch.setattr(retrieval, "retrieve_wikitext2", lambda _req: "wiki")
    request = ContextRetrieverRequest(query="alpha", limit=1, metadata={"retriever": "search"})
    assert router(request) == "wiki"


def test_make_retriever_router_biblicus_fallback(monkeypatch):
    router = retrieval.make_retriever_router({}, {})
    monkeypatch.setattr(retrieval, "retrieve_biblicus_context_pack", lambda _req: "biblicus")
    request = ContextRetrieverRequest(query="alpha", limit=1, metadata={"retriever_id": "other"})
    assert router(request) == "biblicus"


def test_retrieve_biblicus_context_pack_builds_snapshot(tmp_path: Path):
    corpus_root = tmp_path / "corpus"
    corpus = Corpus.init(corpus_root)
    source_dir = corpus_root / "source"
    source_dir.mkdir()
    (source_dir / "cats.txt").write_text("Cats love naps.")
    (source_dir / "dogs.txt").write_text("Dogs love walks.")
    corpus.import_tree(source_dir)

    request = ContextRetrieverRequest(
        query="cats",
        limit=1,
        maximum_total_characters=200,
        metadata={
            "retriever_id": "embedding-index-inmemory",
            "corpus_root": str(corpus_root),
            "configuration": {
                "embedding_provider": {"provider_id": "hash-embedding", "dimensions": 32},
                "maximum_cache_total_items": 100,
            },
        },
    )
    result = retrieval.retrieve_biblicus_context_pack(request)

    assert result.evidence_count == 1
    assert "cats" in result.text.lower() or "dogs" in result.text.lower()
    assert Corpus.open(corpus_root).latest_snapshot_id is not None


def test_download_file_writes_bytes(monkeypatch, tmp_path: Path):
    class DummyResponse:
        def __init__(self, payload: bytes):
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        retrieval.urllib.request,
        "urlopen",
        lambda _url: DummyResponse(b"payload"),
    )
    target = tmp_path / "file.bin"
    retrieval._download_file("http://example.com", target)
    assert target.read_bytes() == b"payload"


def test_sha256_matches(tmp_path: Path):
    target = tmp_path / "file.txt"
    target.write_text("hello")
    expected = hashlib.sha256(b"hello").hexdigest()
    assert retrieval._sha256_matches(target, expected)
    assert not retrieval._sha256_matches(target, "bad")


def test_sha256_matches_missing_file(tmp_path: Path):
    target = tmp_path / "missing.txt"
    assert retrieval._sha256_matches(target, "any") is False
