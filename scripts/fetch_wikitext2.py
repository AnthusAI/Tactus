"""Fetch Wikitext-2 raw parquet files for tests."""

from __future__ import annotations

from tactus.core.retrieval import ensure_wikitext2_raw


def main() -> None:
    ensure_wikitext2_raw()


if __name__ == "__main__":
    main()
