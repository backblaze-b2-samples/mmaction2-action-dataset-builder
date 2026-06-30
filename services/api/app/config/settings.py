from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Backblaze B2 (Standard #3 env var names) ---
    # Region drives the S3 endpoint; we never store the full endpoint URL,
    # so there is no hardcoded region string anywhere in source.
    b2_region: str = "us-west-004"
    b2_application_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    b2_public_url_base: str = ""

    api_port: int = 8000
    # Explicit allowlist by default — covers Next on :3000 and the
    # fallback :3001 it picks if 3000 is busy. Production deploys should
    # override with the exact frontend origin.
    api_cors_origins: str = "http://localhost:3000,http://localhost:3001"
    # Optional dev-only escape hatch: a regex that matches additional
    # allowed origins. Empty by default — set this to e.g.
    # `^http://localhost:\d+$` to accept any localhost port without
    # listing each one. NEVER ship this to production.
    api_cors_origin_regex: str = ""

    # Upload limits — raw broadcast / fitness / security footage can be large.
    # Held fully in memory during ingest (see runtime/upload.py); production
    # should switch to multipart streaming for multi-GB inputs.
    max_file_size: int = 500 * 1024 * 1024  # 500MB

    # Small durable counters (downloads, etc). Point at a persistent
    # volume in production if you care about surviving restarts.
    download_count_file: str = "data/download_count.json"

    # --- Action-dataset builder pipeline ---
    # Uploaded raw footage lands here; the build form and dashboard both
    # list this prefix to find source videos.
    raw_prefix: str = "raw/"
    # Every dataset build (config, segments, clips, annotations, releases) lives
    # under this prefix, isolated per build id so a delete is trivially scoped.
    builds_prefix: str = "builds/"

    # Local engine device — auto-detected at runtime (CUDA -> Apple MPS -> CPU)
    # and defaulting to CPU. "auto" lets the engine pick; set "cpu"/"cuda"/"mps"
    # to force a device. mmcv MPS support is weak, so on Apple Silicon this
    # effectively collapses to CUDA -> CPU (see repo/mmaction_engine.py).
    device: str = "auto"

    # MMAction2 recognizer defaults (overridable per build). Tuned for a quick,
    # no-GPU CPU demo. The model id maps to a bundled MMAction2 config + the
    # Kinetics-400 checkpoint that auto-downloads on first use.
    recognizer_model: str = "tsn-r50-kinetics400"
    confidence_threshold: float = 0.30

    # Segmentation defaults.
    window_seconds: float = 5.0
    stride_seconds: float = 5.0
    # Caps a CPU demo at a manageable number of candidate clips so a build
    # finishes fast even on a long source video.
    max_clips: int = 60

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",")]

    @property
    def b2_endpoint(self) -> str:
        """Derive the S3-compatible endpoint from the region.

        Keeping only the region in config means no hardcoded endpoint /
        region string lives anywhere else in the source tree.
        """
        return f"https://s3.{self.b2_region}.backblazeb2.com"


settings = Settings()
