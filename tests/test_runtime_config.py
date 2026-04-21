from __future__ import annotations

from pathlib import Path

from wheresmymoney.runtime_config import RuntimeConfig


def test_from_env_prefers_dotenv_over_existing_shell_env(
    tmp_path: Path,
    monkeypatch,
) -> None:
    target_config = tmp_path / "target.json"
    target_config.write_text("{}", encoding="utf-8")

    service_account = tmp_path / "service-account.json"
    service_account.write_text("{}", encoding="utf-8")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                f"GOOGLE_SERVICE_ACCOUNT_JSON={service_account}",
                "GEMINI_API_KEY=dotenv-key",
                f"TARGET_SHEET_CONFIG={target_config}",
                "GEMINI_MODEL=gemini-2.5-flash",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("GEMINI_API_KEY", "shell-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")

    runtime_config = RuntimeConfig.from_env(env_file)

    assert runtime_config.gemini_api_key == "dotenv-key"
    assert runtime_config.gemini_model == "gemini-2.5-flash"
