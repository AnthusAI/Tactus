import boto3
from moto import mock_aws

from tactus.registry.storage import S3Storage, download_to_cache, resolve_path


@mock_aws
def test_s3_storage_save_load_exists_list():
    s3 = boto3.client("s3", region_name="us-east-1")
    bucket = "test-bucket"
    s3.create_bucket(Bucket=bucket)

    storage = S3Storage(bucket=bucket, client=s3)
    uri = storage.save(b"hello", "models/model.bin")

    assert uri == "s3://test-bucket/models/model.bin"
    assert storage.exists(uri)
    assert storage.load(uri) == b"hello"

    listed = storage.list("models/")
    assert uri in listed


@mock_aws
def test_download_to_cache_and_resolve_path(tmp_path):
    s3 = boto3.client("s3", region_name="us-east-1")
    bucket = "cache-bucket"
    key = "models/model.pt"
    s3.create_bucket(Bucket=bucket)
    s3.put_object(Bucket=bucket, Key=key, Body=b"cached")
    uri = f"s3://{bucket}/{key}"

    cache_dir = tmp_path / "cache"
    local_path = download_to_cache(uri, cache_dir=str(cache_dir), client=s3)
    assert local_path.startswith(str(cache_dir))

    # Second call should reuse cached file
    again = resolve_path(uri, cache_dir=str(cache_dir), client=s3)
    assert again == local_path
    with open(local_path, "rb") as f:
        assert f.read() == b"cached"
