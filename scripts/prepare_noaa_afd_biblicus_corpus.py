"""
Build a Biblicus corpus and embedding index from NOAA AFD text fixtures.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from biblicus.retrievers import get_retriever
from biblicus.corpus import Corpus


def _resolve_source_dir(source: str | None, wfo: str) -> Path:
    if source:
        return Path(source)
    return Path("tests/fixtures/noaa_afd") / wfo.upper()


def _resolve_corpus_dir(corpus: str | None, wfo: str) -> Path:
    if corpus:
        return Path(corpus)
    return Path("tests/fixtures/noaa_afd_corpus") / wfo.upper()


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a Biblicus NOAA AFD corpus")
    parser.add_argument("--wfo", default="MFL", help="WFO office code")
    parser.add_argument("--source", default=None, help="Source directory of NOAA AFD text files")
    parser.add_argument("--corpus", default=None, help="Destination corpus directory")
    parser.add_argument(
        "--retriever",
        default="embedding-index-file",
        help="Biblicus retriever id (embedding-index-file or embedding-index-inmemory)",
    )
    parser.add_argument(
        "--dimensions",
        type=int,
        default=64,
        help="Embedding dimension for hash-embedding provider",
    )
    parser.add_argument(
        "--maximum-cache-total-items",
        type=int,
        default=None,
        help="Maximum cached vectors per scan batch (optional)",
    )
    parser.add_argument(
        "--snippet-characters",
        type=int,
        default=400,
        help="Snippet length budget for evidence text",
    )
    parser.add_argument("--force", action="store_true", help="Recreate the corpus directory")
    args = parser.parse_args()

    source_dir = _resolve_source_dir(args.source, args.wfo)
    corpus_dir = _resolve_corpus_dir(args.corpus, args.wfo)
    source_dir = source_dir.resolve()
    corpus_dir = corpus_dir.resolve()

    if not source_dir.is_dir():
        raise FileNotFoundError(f"Missing NOAA AFD source directory: {source_dir}")

    if corpus_dir.exists() and not args.force:
        corpus = Corpus.open(corpus_dir)
    else:
        corpus = Corpus.init(corpus_dir, force=True)

    corpus.import_tree(source_dir)
    # Corpus.import_tree copies sidecar metadata files (e.g. *.biblicus.yml). Biblicus will
    # then generate import-metadata for those sidecars as if they were primary documents,
    # creating noisy *.biblicus.yml.biblicus.yml artifacts in the corpus tree.
    for path in (corpus_dir / "raw").rglob("*.biblicus.yml.biblicus.yml"):
        path.unlink(missing_ok=True)

    configuration: dict[str, object] = {}
    if args.retriever in {"embedding-index-file", "embedding-index-inmemory"}:
        configuration["embedding_provider"] = {
            "provider_id": "hash-embedding",
            "dimensions": args.dimensions,
        }
        if args.maximum_cache_total_items is not None:
            configuration["maximum_cache_total_items"] = args.maximum_cache_total_items
    elif args.retriever == "tf-vector":
        configuration = {}
    elif args.retriever == "sqlite-full-text-search":
        configuration["snippet_characters"] = args.snippet_characters
        configuration["chunk_size"] = max(args.snippet_characters * 2, 800)
        configuration["chunk_overlap"] = max(args.snippet_characters // 2, 200)

    retriever = get_retriever(args.retriever)
    snapshot = retriever.build_snapshot(
        corpus,
        configuration_name=f"NOAA AFD ({args.wfo.upper()})",
        configuration=configuration,
    )
    print(f"Corpus: {corpus_dir}")
    print(f"Snapshot id: {snapshot.snapshot_id}")


if __name__ == "__main__":
    main()
