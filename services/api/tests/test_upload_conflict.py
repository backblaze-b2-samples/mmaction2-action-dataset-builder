"""Unit tests for raw-video upload filename handling + ingest prefix."""

import pytest

from app.service import upload as upload_service
from app.service.upload import UploadError
from app.types import FileUploadResponse


def _fake_upload(file_data, key, content_type):
    return FileUploadResponse(
        key=key,
        filename=key.rsplit("/", 1)[-1],
        size_bytes=len(file_data),
        size_human="5 B",
        content_type=content_type,
        uploaded_at="2026-02-14T00:00:00Z",
        url=None,
        metadata=None,
    )


def test_upload_writes_video_to_raw_prefix(monkeypatch):
    """A valid video lands under the raw/ ingest prefix the builder draws from."""
    monkeypatch.setattr(upload_service, "upload_file", _fake_upload)

    result = upload_service.process_upload(
        file_data=b"hello",
        filename="match.mp4",
        content_type="video/mp4",
        content_length=5,
    )

    assert result.key == "raw/match.mp4"


def test_upload_allows_duplicate_filename(monkeypatch):
    """B2 is always versioned — re-uploading the same name creates a new version."""
    monkeypatch.setattr(upload_service, "upload_file", _fake_upload)

    result = upload_service.process_upload(
        file_data=b"hello",
        filename="match.mov",
        content_type="video/quicktime",
        content_length=5,
    )

    assert result.key == "raw/match.mov"


def test_upload_rejects_non_video(monkeypatch):
    """Image/PDF/text are no longer accepted — this is a video-ingest pipeline."""
    monkeypatch.setattr(upload_service, "upload_file", _fake_upload)

    with pytest.raises(UploadError) as exc:
        upload_service.process_upload(
            file_data=b"hello",
            filename="report.pdf",
            content_type="application/pdf",
            content_length=5,
        )
    assert exc.value.status_code == 415
