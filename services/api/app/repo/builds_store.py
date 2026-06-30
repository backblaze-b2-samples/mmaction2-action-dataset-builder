"""B2 data-access helpers for the action-dataset builder.

Confined to repo/ alongside b2_client.py so boto3 never leaks into higher
layers. Covers the read/write surface the build pipeline needs beyond the
file-management basics in b2_client.py:

- get_object_bytes(key)        -> download a raw video for local processing
- put_bytes(key, data, ctype)  -> write trimmed clips / annotation CSVs
- put_json(key, obj)           -> write build.json / segments.json / manifests
- get_json(key)                -> read a build manifest back (list / detail)
- list_keys(prefix)            -> bare key listing for builds / clips / sources
- get_object_stats(prefix)     -> object count + total bytes under a prefix
- delete_prefix(prefix)        -> SCOPED bulk delete of a build's own prefix

Every delete is scoped to a builds/<id>/ prefix — never bucket-wide — so a
delete can never wipe other apps' data sharing the bucket.
"""

import json

from botocore.exceptions import ClientError

from app.config import settings
from app.repo.b2_client import get_s3_client


def get_object_bytes(key: str) -> bytes:
    """Download an object's full body. Raises RuntimeError on S3 failure."""
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=settings.b2_bucket_name, Key=key)
        return response["Body"].read()
    except ClientError as e:
        raise RuntimeError(f"B2 get_object failed for '{key}': {e}") from e


def put_bytes(key: str, data: bytes, content_type: str) -> None:
    """Store raw bytes (clip mp4, annotation CSV). Raises RuntimeError on fail."""
    client = get_s3_client()
    try:
        client.put_object(
            Bucket=settings.b2_bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except ClientError as e:
        raise RuntimeError(f"B2 put_object failed for '{key}': {e}") from e


def put_json(key: str, obj: dict) -> None:
    """Serialize and store a JSON artifact. Raises RuntimeError on failure."""
    body = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    put_bytes(key, body, "application/json")


def get_json(key: str) -> dict | None:
    """Read a JSON artifact. Returns None if the key does not exist."""
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=settings.b2_bucket_name, Key=key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            return None
        raise
    return json.loads(response["Body"].read())


def list_keys(prefix: str = "", max_keys: int = 1000) -> list[str]:
    """Return bare object keys under a prefix, paginating through all pages."""
    client = get_s3_client()
    keys: list[str] = []
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": prefix,
        "MaxKeys": max_keys,
    }
    try:
        while True:
            response = client.list_objects_v2(**kwargs)
            keys.extend(obj["Key"] for obj in response.get("Contents", []))
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 list failed for prefix '{prefix}': {e}") from e
    return keys


def get_object_stats(prefix: str = "") -> dict:
    """Aggregate object count + total bytes under a prefix (paginated)."""
    client = get_s3_client()
    contents: list[dict] = []
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": prefix,
        "MaxKeys": 1000,
    }
    try:
        while True:
            response = client.list_objects_v2(**kwargs)
            contents.extend(response.get("Contents", []))
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 stats query failed for '{prefix}': {e}") from e
    return {
        "total_objects": len(contents),
        "total_size_bytes": sum(obj["Size"] for obj in contents),
    }


def delete_prefix(prefix: str) -> int:
    """Delete every object under a prefix. Returns the count deleted.

    SAFETY: callers must pass a build-scoped prefix (builds/<id>/). This
    refuses an empty / root prefix so a bug can never wipe the whole bucket.
    """
    if not prefix or prefix in ("/", settings.builds_prefix):
        raise ValueError(f"Refusing unscoped delete for prefix '{prefix}'")

    client = get_s3_client()
    keys = list_keys(prefix)
    deleted = 0
    # delete_objects takes up to 1000 keys per request.
    for i in range(0, len(keys), 1000):
        batch = [{"Key": k} for k in keys[i : i + 1000]]
        try:
            client.delete_objects(
                Bucket=settings.b2_bucket_name, Delete={"Objects": batch}
            )
        except ClientError as e:
            raise RuntimeError(f"B2 delete_objects failed for '{prefix}': {e}") from e
        deleted += len(batch)
    return deleted
