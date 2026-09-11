"""
Cloud V1 AI provider policy and credential resolution.

HADIL owns provider credentials. Platform MASTER_ADMIN controls which providers
organizations may use and the model HADIL uses for each provider.
Organizations store only a selected provider name — never models or API keys.

Desktop continues to use HadilLLMConfig (encrypted keys, generator/verifier).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from database.metadata_db import (
    HadilDatabase,
    HadilOrganization,
    HadilPlatformAIProvider,
    metadata_manager,
)

logger = logging.getLogger(__name__)

SAFE_UNAVAILABLE = "Selected AI provider is currently unavailable."
SAFE_NOT_ALLOWED = "This AI provider is not available."
SAFE_UNKNOWN = "Unknown AI provider."
SAFE_NO_SELECTION = "No AI provider is configured for this organization."

# Canonical Cloud providers that exist in ai_modules.providers.
CLOUD_PROVIDERS = ("gemini", "openai", "claude", "sarvam")

PROVIDER_LABELS = {
    "gemini": "Google Gemini",
    "openai": "OpenAI",
    "claude": "Anthropic Claude",
    "sarvam": "Sarvam AI",
}

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o",
    "claude": "claude-3-5-sonnet-20241022",
    "sarvam": "sarvam-2b",
}

# Cloud Render secrets. Values are never stored in Git or the metadata DB.
_CREDENTIAL_ENV = {
    "gemini": "HADIL_GEMINI_API_KEY",
    "openai": "HADIL_OPENAI_API_KEY",
    "claude": "HADIL_ANTHROPIC_API_KEY",
    "sarvam": "HADIL_SARVAM_API_KEY",
}

_CREDENTIAL_FALLBACK_ENV = {
    "gemini": ("GEMINI_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "claude": ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
    "sarvam": ("SARVAM_API_KEY",),
}

_PROVIDER_ALIASES = {
    "google": "gemini",
    "anthropic": "claude",
}


class AIProviderConfigError(Exception):
    """Safe, non-secret configuration error for Cloud AI resolution."""


@dataclass(frozen=True)
class CloudLLMRuntime:
    provider_type: str
    model: str
    api_key: str


def canonicalize_provider(raw: Optional[str]) -> Optional[str]:
    if not raw or not str(raw).strip():
        return None
    value = str(raw).strip().lower()
    value = _PROVIDER_ALIASES.get(value, value)
    if value not in CLOUD_PROVIDERS:
        return None
    return value


def _read_env_secret(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _credential_from_env(provider: str) -> Optional[str]:
    primary = _CREDENTIAL_ENV.get(provider)
    if primary:
        found = _read_env_secret(primary)
        if found:
            return found
    for fallback in _CREDENTIAL_FALLBACK_ENV.get(provider, ()):
        found = _read_env_secret(fallback)
        if found:
            return found
    return None


def credential_configured(provider: str) -> bool:
    canonical = canonicalize_provider(provider)
    if not canonical:
        return False
    return bool(_credential_from_env(canonical))


def _ensure_platform_rows(db) -> None:
    existing = {row.provider_type for row in db.query(HadilPlatformAIProvider).all()}
    for provider in CLOUD_PROVIDERS:
        if provider in existing:
            continue
        db.add(
            HadilPlatformAIProvider(
                provider_type=provider,
                enabled=True,
                model=DEFAULT_MODELS[provider],
            )
        )
    db.commit()


def _row_to_platform_public(row: HadilPlatformAIProvider) -> Dict[str, Any]:
    provider = row.provider_type
    configured = credential_configured(provider)
    return {
        "provider": provider,
        "label": PROVIDER_LABELS.get(provider, provider),
        "enabled": bool(row.enabled),
        "model": row.model or DEFAULT_MODELS.get(provider),
        "credential_configured": configured,
    }


def list_platform_providers() -> List[Dict[str, Any]]:
    db = metadata_manager.get_session()
    try:
        _ensure_platform_rows(db)
        rows = db.query(HadilPlatformAIProvider).all()
        by_id = {row.provider_type: row for row in rows}
        return [_row_to_platform_public(by_id[p]) for p in CLOUD_PROVIDERS if p in by_id]
    finally:
        db.close()


def update_platform_providers(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    db = metadata_manager.get_session()
    try:
        _ensure_platform_rows(db)
        for item in items:
            provider = canonicalize_provider(item.get("provider"))
            if not provider:
                raise ValueError(SAFE_UNKNOWN)
            row = (
                db.query(HadilPlatformAIProvider)
                .filter(HadilPlatformAIProvider.provider_type == provider)
                .first()
            )
            if not row:
                row = HadilPlatformAIProvider(provider_type=provider)
                db.add(row)
            if "enabled" in item and item["enabled"] is not None:
                row.enabled = bool(item["enabled"])
            if item.get("model") is not None:
                model = str(item["model"]).strip()
                row.model = model or DEFAULT_MODELS[provider]
        db.commit()
        rows = db.query(HadilPlatformAIProvider).all()
        by_id = {row.provider_type: row for row in rows}
        return [_row_to_platform_public(by_id[p]) for p in CLOUD_PROVIDERS if p in by_id]
    finally:
        db.close()


def get_platform_provider(provider: str) -> Optional[HadilPlatformAIProvider]:
    canonical = canonicalize_provider(provider)
    if not canonical:
        return None
    db = metadata_manager.get_session()
    try:
        _ensure_platform_rows(db)
        return (
            db.query(HadilPlatformAIProvider)
            .filter(HadilPlatformAIProvider.provider_type == canonical)
            .first()
        )
    finally:
        db.close()


def is_provider_enabled(provider: str) -> bool:
    row = get_platform_provider(provider)
    return bool(row and row.enabled)


def list_org_available_providers() -> List[Dict[str, Any]]:
    return [
        {"provider": item["provider"], "label": item["label"]}
        for item in list_platform_providers()
        if item.get("enabled")
    ]


def get_organization_provider(organization_id: int) -> Optional[str]:
    db = metadata_manager.get_session()
    try:
        org = db.query(HadilOrganization).filter(HadilOrganization.id == organization_id).first()
        if not org:
            return None
        return canonicalize_provider(org.ai_provider)
    finally:
        db.close()


def set_organization_provider(organization_id: int, provider: str) -> str:
    canonical = canonicalize_provider(provider)
    if not canonical:
        raise ValueError(SAFE_UNKNOWN)
    if not is_provider_enabled(canonical):
        raise ValueError(SAFE_NOT_ALLOWED)
    db = metadata_manager.get_session()
    try:
        org = db.query(HadilOrganization).filter(HadilOrganization.id == organization_id).first()
        if not org:
            raise ValueError("Organization not found.")
        org.ai_provider = canonical
        db.commit()
        logger.info("organization_id=%s selected provider=%s", organization_id, canonical)
        return canonical
    finally:
        db.close()


def organization_id_for_database(database_id: Optional[str]) -> Optional[int]:
    if not database_id:
        return None
    db = metadata_manager.get_session()
    try:
        rec = db.query(HadilDatabase).filter(HadilDatabase.id == database_id).first()
        return rec.organization_id if rec else None
    finally:
        db.close()


def resolve_cloud_llm_runtime(database_id: Optional[str] = None, organization_id: Optional[int] = None) -> CloudLLMRuntime:
    """
    Resolve provider + platform model + server credential.
    Never reads client-supplied keys or HadilLLMConfig encrypted keys.
    """
    org_id = organization_id
    if org_id is None:
        org_id = organization_id_for_database(database_id)
    if org_id is None:
        raise AIProviderConfigError(SAFE_UNAVAILABLE)

    selected = get_organization_provider(org_id)
    if not selected:
        raise AIProviderConfigError(SAFE_NO_SELECTION)
    if not is_provider_enabled(selected):
        raise AIProviderConfigError(SAFE_UNAVAILABLE)

    row = get_platform_provider(selected)
    model = (row.model if row and row.model else None) or DEFAULT_MODELS[selected]
    api_key = _credential_from_env(selected)
    configured = bool(api_key)
    logger.info("provider=%s configured=%s", selected, configured)
    if not api_key:
        raise AIProviderConfigError(SAFE_UNAVAILABLE)
    return CloudLLMRuntime(provider_type=selected, model=model, api_key=api_key)
