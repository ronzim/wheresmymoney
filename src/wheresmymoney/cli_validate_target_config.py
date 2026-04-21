from __future__ import annotations

import argparse
import sys
from pathlib import Path

from wheresmymoney.target_config import TargetSheetConfig, TargetSheetConfigError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the target Google Sheet configuration."
    )
    parser.add_argument(
        "config_path",
        nargs="?",
        default="config/target_sheet.example.json",
        help="Path to the target-sheet JSON config file.",
    )
    parser.add_argument(
        "--tab",
        dest="tab_name",
        help="Optional tab name to verify as a writable bank tab.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config_path)

    try:
        config = TargetSheetConfig.from_file(config_path)
        if args.tab_name:
            config.ensure_writable_tab(args.tab_name)
    except TargetSheetConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1

    print(f"Configuration valid: {config_path}")
    print(f"Spreadsheet ID: {config.spreadsheet_id}")
    print(f"Categories sheet: {config.categories_sheet_name}")
    print("Allowed bank tabs: " + ", ".join(config.allowed_bank_tabs))
    print(
        "Protected analysis tabs: "
        + ", ".join(config.protected_analysis_tabs)
    )
    print(f"Transaction start row: {config.transaction_start_row}")
    print("Bank tab columns: " + ", ".join(config.bank_tab_columns))

    if args.tab_name:
        print(f"Writable tab confirmed: {args.tab_name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())