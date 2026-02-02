"""
Build a Biblicus corpus and embedding index from NOAA AFD text fixtures.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from biblicus.backends import get_backend
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
        "--backend",
        default="embedding-index-file",
        help="Biblicus backend id (embedding-index-file or embedding-index-inmemory)",
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

    recipe_config: dict[str, object] = {}
    if args.backend in {"embedding-index-file", "embedding-index-inmemory"}:
        recipe_config["embedding_provider"] = {
            "provider_id": "hash-embedding",
            "dimensions": args.dimensions,
        }
        if args.maximum_cache_total_items is not None:
            recipe_config["maximum_cache_total_items"] = args.maximum_cache_total_items
    elif args.backend == "tf-vector":
        recipe_config = {}
    elif args.backend == "sqlite-full-text-search":
        recipe_config["snippet_characters"] = args.snippet_characters
        recipe_config["chunk_size"] = max(args.snippet_characters * 2, 800)
        recipe_config["chunk_overlap"] = max(args.snippet_characters // 2, 200)

    backend = get_backend(args.backend)
    run = backend.build_run(
        corpus,
        recipe_name=f"NOAA AFD ({args.wfo.upper()})",
        config=recipe_config,
    )
    print(f"Corpus: {corpus_dir}")
    print(f"Run id: {run.run_id}")


if __name__ == "__main__":
    main()
