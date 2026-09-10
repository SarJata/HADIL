"""
Centralized HADIL deployment configuration.

Desktop (Windows V1) and cloud (Render) share the same application code.
Capability flags are derived from HADIL_DEPLOYMENT_MODE rather than
scattered localhost/Render/cloud checks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from fastapi import HTTPException

MODE_DESKTOP = "desktop"
MODE_CLOUD = "cloud"
DEFAULT_JWT_SECRET = "hadil-dev-secret-key-change-in-production-12345"


def resolve_deployment_mode() -> str:
    explicit = (os.getenv("HADIL_DEPLOYMENT_MODE") or "").strip().lower()
    if explicit in (MODE_CLOUD, MODE_DESKTOP):
        return explicit
    # Render injects RENDER=true; treat as cloud only when mode is unset.
    if os.getenv("RENDER"):
        return MODE_CLOUD
    return MODE_DESKTOP


def _split_origins(raw: str) -> List[str]:
    origins: List[str] = []
    for part in (raw or "").split(","):
        cleaned = part.strip().rstrip("/")
        if cleaned and cleaned not in origins:
            origins.append(cleaned)
    return origins


@dataclass(frozen=True)
class DeploymentConfig:
    mode: str
    sqlite_local: bool
    sqlite_upload: bool
    sqlite_file_location: bool
    sqlite_directory_scan: bool
    remote_mysql: bool
    remote_postgresql: bool
    windows_runtime: bool
    native_splash: bool
    system_tray: bool
    browser_auto_launch: bool
    server_shutdown: bool
    bind_host: str
    bind_port: int
    cors_allow_credentials: bool

    @property
    def is_cloud(self) -> bool:
        return self.mode == MODE_CLOUD

    @property
    def is_desktop(self) -> bool:
        return self.mode == MODE_DESKTOP

    def has(self, capability: str) -> bool:
        return bool(getattr(self, capability, False))

    def default_cors_origins(self) -> List[str]:
        if self.is_cloud:
            origins: List[str] = []
            render_url = (os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
            if render_url:
                origins.append(render_url)
            return origins
        return [
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

    def cors_origins(self) -> List[str]:
        origins = list(self.default_cors_origins())
        extra = _split_origins(os.getenv("HADIL_ALLOWED_ORIGINS") or os.getenv("ALLOWED_ORIGINS", ""))
        for origin in extra:
            if origin == "*":
                # Authenticated deployments must never use a wildcard origin.
                continue
            if origin not in origins:
                origins.append(origin)
        return origins

    def metadata_database_url(self) -> Optional[str]:
        url = (os.getenv("HADIL_METADATA_DATABASE_URL") or "").strip()
        return url or None

    def validate_cloud_runtime(self) -> None:
        if not self.is_cloud:
            return
        jwt_secret = os.getenv("HADIL_JWT_SECRET", "")
        if not jwt_secret or jwt_secret == DEFAULT_JWT_SECRET:
            raise RuntimeError(
                "Cloud deployment requires HADIL_JWT_SECRET to be set to a non-default value."
            )
        if not self.metadata_database_url() and not os.getenv("HADIL_METADATA_DB"):
            raise RuntimeError(
                "Cloud deployment requires HADIL_METADATA_DATABASE_URL "
                "(or HADIL_METADATA_DB for explicit test overrides)."
            )

    def public_capabilities(self) -> dict:
        return {
            "deployment_mode": self.mode,
            "sqlite_local": self.sqlite_local,
            "sqlite_upload": self.sqlite_upload,
            "sqlite_file_location": self.sqlite_file_location,
            "sqlite_directory_scan": self.sqlite_directory_scan,
            "remote_mysql": self.remote_mysql,
            "remote_postgresql": self.remote_postgresql,
            "server_shutdown": self.server_shutdown,
            "windows_runtime": self.windows_runtime,
        }

    @classmethod
    def from_env(cls) -> "DeploymentConfig":
        mode = resolve_deployment_mode()
        is_cloud = mode == MODE_CLOUD
        port_raw = os.getenv("PORT")
        if port_raw:
            bind_port = int(port_raw)
        else:
            bind_port = 8000
        if is_cloud:
            bind_host = os.getenv("HOST") or "0.0.0.0"
        else:
            bind_host = os.getenv("HOST") or "127.0.0.1"
        return cls(
            mode=mode,
            sqlite_local=not is_cloud,
            sqlite_upload=not is_cloud,
            sqlite_file_location=not is_cloud,
            sqlite_directory_scan=not is_cloud,
            remote_mysql=True,
            remote_postgresql=True,
            windows_runtime=not is_cloud,
            native_splash=not is_cloud,
            system_tray=not is_cloud,
            browser_auto_launch=not is_cloud,
            server_shutdown=not is_cloud,
            bind_host=bind_host,
            bind_port=bind_port,
            cors_allow_credentials=True,
        )


def get_deployment_config() -> DeploymentConfig:
    return DeploymentConfig.from_env()


def require_capability(capability: str):
    """FastAPI dependency: fail closed when a desktop-only capability is used in cloud mode."""

    def _check():
        cfg = get_deployment_config()
        if not cfg.has(capability):
            raise HTTPException(
                status_code=403,
                detail=f"This operation is not available in {cfg.mode} deployment mode.",
            )
        return cfg

    return _check


def is_sqlite_uri(uri: str) -> bool:
    if not uri:
        return False
    lowered = uri.strip().lower()
    return lowered.startswith("sqlite:") or lowered.startswith("file:")
