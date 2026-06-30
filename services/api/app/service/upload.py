import hashlib
import re
from datetime import UTC, datetime

from app.config import settings
from app.repo import upload_file
from app.types import FileMetadataDetail, FileUploadResponse
from app.types.formatting import humanize_bytes

# Raw video ingest is the on-ramp for the dataset builder. We accept the common
# container formats MMAction2 / ffmpeg can decode; everything else is rejected
# at the boundary so a build never chokes on an undecodable upload.
ALLOWED_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
    "video/x-msvideo",
    "video/mpeg",
}

MIME_EXTENSION_MAP: dict[str, set[str]] = {
    "video/mp4": {"mp4", "m4v"},
    "video/quicktime": {"mov"},
    "video/x-matroska": {"mkv"},
    "video/webm": {"webm"},
    "video/x-msvideo": {"avi"},
    "video/mpeg": {"mpeg", "mpg"},
}

_SAFE_FILENAME_RE = re.compile(r"[^\w\-.]")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename: strip path components, remove unsafe chars, limit length."""
    name = filename.replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "")
    name = _SAFE_FILENAME_RE.sub("_", name)
    name = re.sub(r"[_.]{2,}", "_", name)
    name = name.lstrip(".").strip()
    if len(name) > 200:
        base, _, ext = name.rpartition(".")
        name = base[: 200 - len(ext) - 1] + "." + ext if ext else name[:200]
    return name or "unnamed"


def validate_extension_matches_type(filename: str, content_type: str) -> bool:
    """Verify the file extension is consistent with the declared MIME type."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed_exts = MIME_EXTENSION_MAP.get(content_type)
    if allowed_exts is None:
        return False
    if not ext:
        return True
    return ext in allowed_exts


def _basic_metadata(
    file_data: bytes, filename: str, content_type: str
) -> FileMetadataDetail:
    """Content hashes + size only — no EXIF/PDF extraction (trimmed feature)."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return FileMetadataDetail(
        filename=filename,
        size_bytes=len(file_data),
        size_human=humanize_bytes(len(file_data)),
        mime_type=content_type,
        extension=extension,
        md5=hashlib.md5(file_data, usedforsecurity=False).hexdigest(),
        sha256=hashlib.sha256(file_data).hexdigest(),
        uploaded_at=datetime.now(UTC),
    )


class UploadError(Exception):
    """Raised when upload validation fails."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def process_upload(
    file_data: bytes,
    filename: str,
    content_type: str,
    content_length: int | None = None,
) -> FileUploadResponse:
    """Validate and store a raw video under raw/. Raises UploadError on failure."""
    if not filename:
        raise UploadError("No filename provided")

    if content_length and content_length > settings.max_file_size:
        raise UploadError(
            f"File too large. Max size: {humanize_bytes(settings.max_file_size)}",
            status_code=413,
        )

    if content_type not in ALLOWED_TYPES:
        raise UploadError(
            f"File type '{content_type}' not allowed — upload a video container "
            "(mp4, mov, mkv, webm, avi, mpeg)",
            status_code=415,
        )

    safe_name = sanitize_filename(filename)

    if not validate_extension_matches_type(safe_name, content_type):
        raise UploadError(
            "File extension does not match declared content type",
            status_code=415,
        )

    if len(file_data) == 0:
        raise UploadError("Empty file")

    if len(file_data) > settings.max_file_size:
        raise UploadError(
            f"File too large. Max size: {humanize_bytes(settings.max_file_size)}",
            status_code=413,
        )

    # Raw footage lands under raw/ — the ingest pool every build draws from.
    # B2 buckets are versioned; re-uploading the same key creates a new version.
    key = f"{settings.raw_prefix}{safe_name}"
    result = upload_file(file_data, key, content_type)
    metadata = _basic_metadata(file_data, safe_name, content_type)

    return FileUploadResponse(
        key=result.key,
        filename=result.filename,
        size_bytes=result.size_bytes,
        size_human=result.size_human,
        content_type=content_type,
        uploaded_at=result.uploaded_at,
        url=result.url,
        metadata=metadata,
    )
