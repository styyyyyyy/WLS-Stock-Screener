"""Convenience entry point for running the project without installation."""

from pathlib import Path
import sys

# Allow ``python run_screener.py`` directly from a fresh clone.
PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from wls_screener.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
