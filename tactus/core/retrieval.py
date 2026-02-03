"""Deterministic retrieval utilities for Context packs."""

from __future__ import annotations

import hashlib
import os
import re
import urllib.request
from pathlib import Path
from typing import Iterable, List

import pyarrow.parquet as pq

from biblicus.context import ContextPack, ContextPackBlock
from biblicus.context_engine import ContextRetrieverRequest, retrieve_context_pack
from biblicus.corpus import Corpus


_WIKITEXT2_FILES = {
    "train": {
        "filename": "train-00000-of-00001.parquet",
        "sha256": "e83889baabc497075506f91975be5fac0d45c5290b6b20582c8cd1e853d0c9f7",
    },
    "validation": {
        "filename": "validation-00000-of-00001.parquet",
        "sha256": "204929b7ff9d6184953f867dedb860e40aa69c078fc1e54b3baaa8fb28511c4c",
    },
    "test": {
        "filename": "test-00000-of-00001.parquet",
        "sha256": "5f1bea067869d04849c0f975a2b29c4ff47d867f484f5010ea5e861eab246d91",
    },
}


def get_wikitext2_cache_dir() -> Path:
    """Return the cache directory for Wikitext-2 raw parquet files."""
    env_path = os.environ.get("TACTUS_WIKITEXT2_CACHE_DIR")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wikitext-2-raw-v1"


def ensure_wikitext2_raw(cache_dir: Path | None = None) -> Path:
    """Ensure the Wikitext-2 raw parquet files are present."""
    cache_dir = cache_dir or get_wikitext2_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    base_url = (
        "https://huggingface.co/datasets/Salesforce/wikitext/resolve/main/" "wikitext-2-raw-v1"
    )

    for split, meta in _WIKITEXT2_FILES.items():
        target = cache_dir / meta["filename"]
        if target.exists() and _sha256_matches(target, meta["sha256"]):
            continue
        url = f"{base_url}/{meta['filename']}"
        _download_file(url, target)
        if not _sha256_matches(target, meta["sha256"]):
            raise RuntimeError(f"Checksum mismatch for {split} parquet file")
    return cache_dir


def load_wikitext2_texts(split: str, limit: int | None = None) -> List[str]:
    """Load Wikitext-2 raw texts for the given split."""
    if split not in _WIKITEXT2_FILES:
        raise ValueError(f"Unknown Wikitext2 split: {split}")
    cache_dir = ensure_wikitext2_raw()
    parquet_path = cache_dir / _WIKITEXT2_FILES[split]["filename"]
    table = pq.read_table(parquet_path, columns=["text"])
    texts = [value for value in table.column("text").to_pylist() if value]
    if limit is not None:
        return texts[:limit]
    return texts


def retrieve_wikitext2(request: ContextRetrieverRequest) -> ContextPack:
    """
    Retrieve matching passages from Wikitext-2 raw.

    :param request: Context retriever request payload.
    :type request: ContextRetrieverRequest
    :return: Context pack derived from matching passages.
    :rtype: ContextPack
    """
    split = request.metadata.get("split", "train")
    maximum_cache_total_items = request.metadata.get("maximum_cache_total_items")
    maximum_cache_total_characters = request.metadata.get("maximum_cache_total_characters")
    texts = load_wikitext2_texts(split=split, limit=None)
    if maximum_cache_total_items is not None:
        texts = texts[: int(maximum_cache_total_items)]
    elif maximum_cache_total_characters is not None:
        selected = []
        total_chars = 0
        for text in texts:
            text_length = len(text)
            if total_chars + text_length > int(maximum_cache_total_characters):
                break
            selected.append(text)
            total_chars += text_length
        texts = selected
    ranked = _rank_texts(request.query, texts)
    offset = request.offset
    limit = request.limit

    blocks: List[ContextPackBlock] = []
    remaining_chars = request.maximum_total_characters
    for idx, text in enumerate(ranked[offset : offset + limit], start=1):
        snippet = text.strip()
        if remaining_chars is not None and remaining_chars <= 0:
            break
        if remaining_chars is not None and len(snippet) > remaining_chars:
            snippet = snippet[: remaining_chars - 3].rstrip() + "..."
        if remaining_chars is not None:
            remaining_chars -= len(snippet)
        if not snippet:
            continue
        blocks.append(
            ContextPackBlock(
                evidence_item_id=f"{split}-{offset + idx}",
                text=snippet,
                metadata=None,
            )
        )

    text = "\n\n".join(block.text for block in blocks)
    return ContextPack(text=text, evidence_count=len(blocks), blocks=blocks)


def get_noaa_afd_cache_dir() -> Path:
    """Return the cache directory for NOAA AFD text fixtures."""
    env_path = os.environ.get("TACTUS_NOAA_AFD_DIR")
    if env_path:
        return Path(env_path)
    return Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "noaa_afd"


def load_noaa_afd_texts(wfo: str, limit: int | None = None) -> List[str]:
    """Load NOAA AFD text files for the given WFO code."""
    base_dir = get_noaa_afd_cache_dir() / wfo.upper()
    if not base_dir.exists():
        raise FileNotFoundError(f"No NOAA AFD corpus found for WFO '{wfo}' at {base_dir}")
    files = sorted(path for path in base_dir.glob("*.txt"))
    texts = [path.read_text(encoding="utf-8", errors="replace") for path in files]
    if limit is not None:
        return texts[:limit]
    return texts


def retrieve_noaa_afd(request: ContextRetrieverRequest) -> ContextPack:
    """
    Retrieve matching passages from NOAA AFD text fixtures.

    :param request: Context retriever request payload.
    :type request: ContextRetrieverRequest
    :return: Context pack derived from matching passages.
    :rtype: ContextPack
    """
    wfo = request.metadata.get("wfo", "MFL")
    maximum_cache_total_items = request.metadata.get("maximum_cache_total_items")
    maximum_cache_total_characters = request.metadata.get("maximum_cache_total_characters")
    texts = load_noaa_afd_texts(wfo=wfo, limit=None)
    if maximum_cache_total_items is not None:
        texts = texts[: int(maximum_cache_total_items)]
    elif maximum_cache_total_characters is not None:
        selected = []
        total_chars = 0
        for text in texts:
            text_length = len(text)
            if total_chars + text_length > int(maximum_cache_total_characters):
                break
            selected.append(text)
            total_chars += text_length
        texts = selected

    ranked = _rank_texts(request.query, texts)
    offset = request.offset
    limit = request.limit

    blocks: List[ContextPackBlock] = []
    remaining_chars = request.maximum_total_characters
    for idx, text in enumerate(ranked[offset : offset + limit], start=1):
        snippet = text.strip()
        if remaining_chars is not None and remaining_chars <= 0:
            break
        if remaining_chars is not None and len(snippet) > remaining_chars:
            snippet = snippet[: remaining_chars - 3].rstrip() + "..."
        if remaining_chars is not None:
            remaining_chars -= len(snippet)
        if not snippet:
            continue
        blocks.append(
            ContextPackBlock(
                evidence_item_id=f"{wfo.lower()}-{offset + idx}",
                text=snippet,
                metadata=None,
            )
        )

    text = "\n\n".join(block.text for block in blocks)
    return ContextPack(text=text, evidence_count=len(blocks), blocks=blocks)


def retrieve_biblicus_context_pack(request: ContextRetrieverRequest) -> ContextPack:
    """
    Retrieve a context pack using Biblicus retrievers.

    :param request: Context retriever request payload.
    :type request: ContextRetrieverRequest
    :return: Context pack derived from Biblicus retrieval.
    :rtype: ContextPack
    :raises ValueError: If required metadata is missing.
    """
    metadata = request.metadata or {}
    retriever_id = metadata.get("retriever_id") or metadata.get("retriever_type")
    corpus_root = metadata.get("corpus_root") or metadata.get("root")
    if not retriever_id:
        raise ValueError("Biblicus retrieval requires 'retriever_id' in metadata")
    if not corpus_root:
        raise ValueError("Biblicus retrieval requires 'corpus_root' in metadata")

    snapshot_id = metadata.get("snapshot_id")
    configuration_name = metadata.get("configuration_name")
    configuration = metadata.get("configuration") or {}
    maximum_items_per_source = metadata.get(
        "maximum_items_per_source",
        metadata.get("max_items_per_source"),
    )
    include_metadata = bool(metadata.get("include_metadata", False))
    metadata_fields = metadata.get("metadata_fields")

    corpus = Corpus.open(corpus_root)
    return retrieve_context_pack(
        request=request,
        corpus=corpus,
        retriever_id=retriever_id,
        snapshot_id=snapshot_id,
        configuration_name=configuration_name,
        configuration=configuration,
        max_items_per_source=maximum_items_per_source,
        include_metadata=include_metadata,
        metadata_fields=metadata_fields,
    )


def make_retriever_router(corpus_registry, retriever_registry=None) -> callable:
    """
    Build a retriever dispatcher based on corpus and retriever configuration.

    :param corpus_registry: Corpus registry used to resolve corpus metadata.
    :type corpus_registry: dict[str, Any] or None
    :param retriever_registry: Retriever registry used to resolve retrievers.
    :type retriever_registry: dict[str, Any] or None
    :return: Retriever callable that dispatches by retriever id.
    :rtype: callable
    """

    def _route(request: ContextRetrieverRequest) -> ContextPack:
        corpus_name = request.metadata.get("corpus")
        retriever_name = request.metadata.get("retriever")
        retriever_id = request.metadata.get("retriever_id") or request.metadata.get(
            "retriever_type"
        )
        if retriever_id is None and retriever_registry and retriever_name in retriever_registry:
            retriever_spec = retriever_registry[retriever_name]
            retriever_config = retriever_spec.config if hasattr(retriever_spec, "config") else {}
            if isinstance(retriever_config, dict):
                retriever_id = retriever_config.get("retriever_id") or retriever_config.get(
                    "retriever_type"
                )

        if retriever_id == "noaa_afd":
            return retrieve_noaa_afd(request)
        if retriever_id == "wikitext2":
            return retrieve_wikitext2(request)

        if retriever_id is None:
            missing_target = retriever_name or corpus_name or "<unknown>"
            raise ValueError(f"Missing retriever_id for retriever '{missing_target}'")

        return retrieve_biblicus_context_pack(request)

    return _route


def _rank_texts(query: str, texts: Iterable[str]) -> List[str]:
    """Rank texts by keyword overlap."""
    query_terms = _tokenize(query)
    if not query_terms:
        return list(texts)
    scored = []
    for text in texts:
        text_terms = _tokenize(text)
        score = sum(text_terms.count(term) for term in query_terms)
        scored.append((score, text))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [text for score, text in scored if score > 0] or list(texts)


def _tokenize(text: str) -> List[str]:
    """Tokenize text to lowercase word tokens."""
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _download_file(url: str, target: Path) -> None:
    """Download a file to the target path."""
    with urllib.request.urlopen(url) as response, target.open("wb") as handle:
        handle.write(response.read())


def _sha256_matches(path: Path, expected: str) -> bool:
    """Check SHA256 checksum of a file."""
    if not path.exists():
        return False
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest() == expected
