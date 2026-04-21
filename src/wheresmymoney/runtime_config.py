from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class RuntimeConfigError(ValueError):
    pass


DEFAULT_TARGET_CONFIG_PATH = "config/target_sheet.example.json"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


@dataclass(frozen=True)
class RuntimeConfig:
    google_service_account_json: Path | None
    gemini_api_key: str | None
    target_sheet_config_path: Path
    gemini_model: str = DEFAULT_GEMINI_MODEL

    @classmethod
    def from_env(
        cls,
        env_path: str | Path | None = None,
        *,
        allow_missing_secrets: bool = False,
    ) -> "RuntimeConfig":
        _load_dotenv_if_available(env_path)

        google_credentials = _load_path_env(
            "GOOGLE_SERVICE_ACCOUNT_JSON",
            allow_missing=allow_missing_secrets,
        )
        gemini_api_key = _load_string_env(
            "GEMINI_API_KEY",
            allow_missing=allow_missing_secrets,
        )
        target_sheet_config_path = _load_path_env(
            "TARGET_SHEET_CONFIG",
            default=DEFAULT_TARGET_CONFIG_PATH,
        )
        gemini_model = _load_string_env(
            "GEMINI_MODEL",
            default=DEFAULT_GEMINI_MODEL,
        )

        return cls(
            google_service_account_json=google_credentials,
            gemini_api_key=gemini_api_key,
            target_sheet_config_path=target_sheet_config_path,
            gemini_model=gemini_model,
        )


def _load_dotenv_if_available(env_path: str | Path | None) -> None:
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return

    if env_path is None:
        load_dotenv(override=True)
    else:
        load_dotenv(dotenv_path=Path(env_path), override=True)


def _require_non_empty_env(value: str | None, env_name: str) -> str:
    if value is None or not value.strip():
        raise RuntimeConfigError(
            f"Missing required environment variable: {env_name}"
        )
    return value.strip()


def _require_existing_path(value: str | None, env_name: str) -> Path:
    normalized = _require_non_empty_env(value, env_name)
    path = Path(normalized)
    if not path.exists():
        raise RuntimeConfigError(
            f"Path defined by {env_name} does not exist: {path}"
        )
    return path


def _load_string_env(
    env_name: str,
    *,
    default: str | None = None,
    allow_missing: bool = False,
) -> str | None:
    value = os.getenv(env_name, default)
    if allow_missing and (value is None or not str(value).strip()):
        return None
    return _require_non_empty_env(value, env_name)


def _load_path_env(
    env_name: str,
    *,
    default: str | None = None,
    allow_missing: bool = False,
) -> Path | None:
    value = os.getenv(env_name, default)
    if allow_missing and (value is None or not str(value).strip()):
        return None
    return _require_existing_path(value, env_name)
