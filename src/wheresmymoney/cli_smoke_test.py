from __future__ import annotations

import argparse
import sys

from wheresmymoney.runtime_config import RuntimeConfig, RuntimeConfigError
from wheresmymoney.target_config import TargetSheetConfig, TargetSheetConfigError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run smoke checks for local config, Google Sheets, and Gemini."
    )
    parser.add_argument(
        "--env-file",
        dest="env_file",
        help="Optional path to a dotenv file.",
    )
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Validate only local configuration without contacting external APIs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        runtime_config = RuntimeConfig.from_env(
            args.env_file,
            allow_missing_secrets=args.config_only,
        )
        target_config = TargetSheetConfig.from_file(
            runtime_config.target_sheet_config_path
        )
    except (RuntimeConfigError, TargetSheetConfigError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    print("Runtime configuration loaded.")
    print(f"Target config: {runtime_config.target_sheet_config_path}")
    print(f"Spreadsheet ID: {target_config.spreadsheet_id}")
    print(f"Gemini model: {runtime_config.gemini_model}")

    if args.config_only:
        print("Config-only mode enabled. External API checks skipped.")
        return 0

    try:
        sheet_names = fetch_sheet_names(runtime_config, target_config)
        print("Google Sheets OK: " + ", ".join(sheet_names))
    except Exception as exc:  # pragma: no cover - external integration path
        print(
            "Google Sheets smoke test failed: "
            f"{exc.__class__.__name__}: {exc!r}",
            file=sys.stderr,
        )
        return 1

    try:
        reply_text = check_gemini(runtime_config)
        print(f"Gemini OK: {reply_text}")
    except Exception as exc:  # pragma: no cover - external integration path
        print(
            "Gemini smoke test failed: "
            f"{exc.__class__.__name__}: {exc!r}",
            file=sys.stderr,
        )
        return 1

    return 0


def fetch_sheet_names(
    runtime_config: RuntimeConfig, target_config: TargetSheetConfig
) -> list[str]:
    import gspread

    if runtime_config.google_service_account_json is None:
        raise RuntimeConfigError(
            "GOOGLE_SERVICE_ACCOUNT_JSON is required for external smoke tests"
        )

    client = gspread.service_account(
        filename=str(runtime_config.google_service_account_json)
    )
    spreadsheet = client.open_by_key(target_config.spreadsheet_id)
    return [worksheet.title for worksheet in spreadsheet.worksheets()]


def check_gemini(runtime_config: RuntimeConfig) -> str:
    from google import genai

    if runtime_config.gemini_api_key is None:
        raise RuntimeConfigError(
            "GEMINI_API_KEY is required for external smoke tests"
        )

    client = genai.Client(api_key=runtime_config.gemini_api_key)
    response = client.models.generate_content(
        model=runtime_config.gemini_model,
        contents="Reply with exactly: hello world",
    )
    return response.text.strip()


if __name__ == "__main__":
    raise SystemExit(main())