"""
Fetch recent NOAA/NWS Area Forecast Discussions (AFD) via RSS and store as text.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
import re
import yaml


RSS_TEMPLATES = (
    "https://www.weather.gov/source/{wfo}/rss/AFD/AFD.xml",
    "https://weather.gov/source/{wfo}/rss/AFD/AFD.xml",
    "http://weather.gov/source/{wfo}/rss/AFD/AFD.xml",
)

RSS_INDEX_TEMPLATE = "https://www.weather.gov/{wfo}/rss"
NWS_API_PRODUCTS = "https://api.weather.gov/products/types/AFD/locations/{wfo}"
NWS_API_PRODUCT = "https://api.weather.gov/products/{product_id}"


@dataclass
class AfdItem:
    title: str
    published: str
    link: str
    text: str


def _fetch_rss(urls: list[str]) -> str:
    last_error = None
    for url in urls:
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "tactus-demo/1.0 (context-engine demo; contact: devnull@example.com)"
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No RSS URL candidates provided.")


def _discover_afd_url(wfo: str) -> list[str]:
    index_url = RSS_INDEX_TEMPLATE.format(wfo=wfo.lower())
    try:
        req = urllib.request.Request(
            index_url,
            headers={
                "User-Agent": "tactus-demo/1.0 (context-engine demo; contact: devnull@example.com)"
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    matches = re.findall(r"https?://[^\\s\"']+AFD\\.xml", html, flags=re.IGNORECASE)
    return list(dict.fromkeys(matches))


def _parse_items(xml_text: str) -> list[AfdItem]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        published = (item.findtext("pubDate") or "").strip()
        link = (item.findtext("link") or "").strip()
        description = (item.findtext("description") or "").strip()
        text = description.replace("&lt;", "<").replace("&gt;", ">")
        items.append(AfdItem(title=title, published=published, link=link, text=text))
    return items


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "tactus-demo/1.0 (context-engine demo; contact: devnull@example.com)",
            "Accept": "application/ld+json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _fetch_nws_api_items(wfo: str, max_items: int) -> list[AfdItem]:
    listing_url = NWS_API_PRODUCTS.format(wfo=wfo.upper())
    listing = _fetch_json(listing_url)
    products = listing.get("@graph", [])[:max_items]
    items: list[AfdItem] = []
    for product in products:
        product_id = product.get("id")
        if not product_id:
            continue
        detail = _fetch_json(NWS_API_PRODUCT.format(product_id=product_id))
        text = (detail.get("productText") or "").strip()
        items.append(
            AfdItem(
                title=detail.get("productName", "") or product.get("name", ""),
                published=detail.get("issuanceTime", ""),
                link=detail.get("@id", ""),
                text=text,
            )
        )
    return items


def _safe_slug(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text)[:80]


def _write_items(items: list[AfdItem], output_dir: Path, max_items: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for idx, item in enumerate(items[:max_items], start=1):
        slug = _safe_slug(item.title or f"afd_{idx}")
        text_path = output_dir / f"{idx:02d}_{slug}.txt"
        meta_path = output_dir / f"{idx:02d}_{slug}.json"
        sidecar_path = text_path.with_name(text_path.name + ".biblicus.yml")
        text_path.write_text(item.text.strip() + "\n", encoding="utf-8")
        meta = {
            "title": item.title,
            "published": item.published,
            "link": item.link,
        }
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        sidecar_path.write_text(
            yaml.safe_dump(meta, sort_keys=False).strip() + "\n", encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch NOAA AFD RSS items")
    parser.add_argument(
        "--wfo",
        action="append",
        default=None,
        help="WFO office code (can be repeated). Default: TSA",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=5,
        help="Maximum number of items per WFO",
    )
    parser.add_argument(
        "--output",
        default="tests/fixtures/noaa_afd",
        help="Output directory for corpus files",
    )
    args = parser.parse_args()
    if not args.wfo:
        args.wfo = ["TSA"]

    output_root = Path(args.output)
    total = 0
    for wfo in args.wfo:
        candidates = _discover_afd_url(wfo)
        if not candidates:
            candidates = [template.format(wfo=wfo.lower()) for template in RSS_TEMPLATES] + [
                template.format(wfo=wfo.upper()) for template in RSS_TEMPLATES
            ]
        items = []
        try:
            xml_text = _fetch_rss(candidates)
            items = _parse_items(xml_text)
        except Exception:
            items = _fetch_nws_api_items(wfo, args.max_items)
        target_dir = output_root / wfo.upper()
        _write_items(items, target_dir, args.max_items)
        print(f"Fetched {min(len(items), args.max_items)} items for {wfo.upper()}")
        total += min(len(items), args.max_items)
        time.sleep(0.2)

    print(f"Stored {total} AFD documents in {output_root}")


if __name__ == "__main__":
    main()
