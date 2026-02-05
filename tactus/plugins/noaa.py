"""
NOAA AFD helper tools for Tactus demos.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def fetch_noaa_afd(
    *,
    wfo: str,
    max_items: int = 5,
    output_root: str = "tests/fixtures/noaa_afd",
    corpus_root: str = "tests/fixtures/noaa_afd_corpus",
    force: bool = True,
) -> Dict[str, Any]:
    """
    Fetch NOAA AFD fixtures and import them into a Biblicus corpus (no index).

    :param wfo: Weather Forecast Office code (e.g., MFL).
    :type wfo: str
    :param max_items: Maximum number of items to fetch.
    :type max_items: int
    :param output_root: Directory for raw fixture output.
    :type output_root: str
    :param corpus_root: Directory for Biblicus corpus output.
    :type corpus_root: str
    :param force: Whether to recreate the corpus directory.
    :type force: bool
    :return: Summary of the fetch/import operation.
    :rtype: dict[str, Any]
    """
    repo_root = Path(__file__).resolve().parents[2]
    fetch_script = repo_root / "scripts" / "fetch_noaa_afd_corpus.py"
    prepare_script = repo_root / "scripts" / "prepare_noaa_afd_biblicus_corpus.py"

    output_root_path = Path(output_root)
    corpus_root_path = Path(corpus_root) / wfo.upper()

    fetch_args = [
        sys.executable,
        str(fetch_script),
        "--wfo",
        wfo,
        "--max-items",
        str(max_items),
        "--output",
        str(output_root_path),
    ]
    subprocess.run(fetch_args, check=True)

    prepare_args = [
        sys.executable,
        str(prepare_script),
        "--wfo",
        wfo,
        "--corpus",
        str(corpus_root_path),
        "--no-index",
    ]
    if force:
        prepare_args.append("--force")
    subprocess.run(prepare_args, check=True)

    return {
        "status": "ok",
        "wfo": wfo,
        "max_items": max_items,
        "output_root": str(output_root_path),
        "corpus_root": str(corpus_root_path),
        "indexed": False,
    }
