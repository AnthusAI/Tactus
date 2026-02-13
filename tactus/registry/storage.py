"""
Storage abstractions for model artifacts.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Protocol, Tuple

import boto3
from botocore.exceptions import ClientError


class ModelStorage(Protocol):
    """Protocol for model artifact storage backends."""

    def save(self, artifact: bytes, path: str) -> str:
        """
        Save a model artifact and return a URI/location string.

        Args:
            artifact: Raw bytes of the artifact.
            path: Storage path (relative key or full URI, backend dependent).
        """
        ...

    def load(self, uri: str) -> bytes:
        """Load artifact bytes from a URI or key."""
        ...

    def exists(self, uri: str) -> bool:
        """Return True if the artifact exists at the given URI/key."""
        ...

    def list(self, prefix: Optional[str] = None) -> List[str]:
        """List artifact URIs/keys under an optional prefix."""
        ...


class LocalStorage:
    """Filesystem-based storage implementation."""

    def __init__(self, base_dir: Optional[str] = None):
        # Default to ~/.tactus/models/artifacts
        if base_dir is None:
            base_dir = os.path.expanduser("~/.tactus/models/artifacts")
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, path: str) -> Path:
        raw = Path(path)
        if raw.is_absolute():
            return raw
        return self.base_dir / raw

    def save(self, artifact: bytes, path: str) -> str:
        dest = self._resolve_path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            f.write(artifact)
        return str(dest)

    def load(self, uri: str) -> bytes:
        dest = self._resolve_path(uri)
        with open(dest, "rb") as f:
            return f.read()

    def exists(self, uri: str) -> bool:
        return self._resolve_path(uri).exists()

    def list(self, prefix: Optional[str] = None) -> List[str]:
        root = self._resolve_path(prefix) if prefix else self.base_dir
        if not root.exists():
            return []
        results: List[str] = []
        for path in root.rglob("*"):
            if path.is_file():
                results.append(str(path))
        return results


def _parse_s3_uri(uri: str) -> Tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {uri}")
    without_scheme = uri[len("s3://") :]
    parts = without_scheme.split("/", 1)
    if len(parts) != 2 or not parts[0]:
        raise ValueError(f"Invalid S3 URI: {uri}")
    bucket, key = parts
    return bucket, key


class S3Storage:
    """S3-backed storage using boto3."""

    def __init__(self, bucket: str, prefix: str = "", client=None, region_name: str = "us-east-1"):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.s3 = client or boto3.client("s3", region_name=region_name)

    def _full_key(self, path: str) -> str:
        if path.startswith("s3://"):
            _, key = _parse_s3_uri(path)
            return key
        if self.prefix:
            return f"{self.prefix}/{path.lstrip('/')}"
        return path.lstrip("/")

    def save(self, artifact: bytes, path: str) -> str:
        key = self._full_key(path)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=artifact)
        return f"s3://{self.bucket}/{key}"

    def load(self, uri: str) -> bytes:
        bucket, key = _parse_s3_uri(uri) if uri.startswith("s3://") else (self.bucket, self._full_key(uri))
        resp = self.s3.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()

    def exists(self, uri: str) -> bool:
        bucket, key = _parse_s3_uri(uri) if uri.startswith("s3://") else (self.bucket, self._full_key(uri))
        try:
            self.s3.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404 or e.response.get(
                "Error", {}
            ).get("Code") in {"404", "NoSuchKey"}:
                return False
            raise

    def list(self, prefix: Optional[str] = None) -> List[str]:
        key_prefix = self._full_key(prefix or "")
        resp = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=key_prefix)
        contents = resp.get("Contents", [])
        return [f"s3://{self.bucket}/{obj['Key']}" for obj in contents]


def download_to_cache(uri: str, cache_dir: Optional[str] = None, client=None) -> str:
    """
    Download an S3 URI to a local cache directory (idempotent).

    Returns the local file path.
    """
    bucket, key = _parse_s3_uri(uri)
    cache_root = Path(cache_dir or os.path.expanduser("~/.tactus/cache/models"))
    local_path = cache_root / bucket / key
    if local_path.exists():
        return str(local_path)

    local_path.parent.mkdir(parents=True, exist_ok=True)
    s3 = client or boto3.client("s3")
    s3.download_file(bucket, key, str(local_path))
    return str(local_path)


def resolve_path(path: str, cache_dir: Optional[str] = None, client=None) -> str:
    """
    Resolve a path, downloading S3 URIs to local cache if needed.
    """
    if path.startswith("s3://"):
        return download_to_cache(path, cache_dir=cache_dir, client=client)
    return path
