"""
BdfDiff – Application entry point.

Usage:
    python run.py [--repo PATH] [--host HOST] [--port PORT] [--debug]

The --repo flag sets the Git repository path that BdfDiff will use for
commit-history features. Defaults to the current working directory.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from the project root without installing the package.
sys.path.insert(0, os.path.dirname(__file__))

from app.routes import create_app


def _read_local_repo_path() -> str | None:
    """Read repo_path from a local, git-ignored config file if present."""
    local_cfg = Path(__file__).resolve().parent / ".bdfdiff.local.json"
    if not local_cfg.exists():
        return None

    try:
        data = json.loads(local_cfg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    repo_path = data.get("repo_path")
    return repo_path if isinstance(repo_path, str) and repo_path.strip() else None


def main() -> None:
    local_repo = _read_local_repo_path()
    env_repo = os.environ.get("REPO_PATH")
    default_repo = local_repo or env_repo or "."

    parser = argparse.ArgumentParser(
        description="BdfDiff – Nastran BDF visual diff tool"
    )
    parser.add_argument(
        "--repo",
        default=default_repo,
        help=(
            "Path to the Git repository containing BDF files "
            "(priority: --repo > .bdfdiff.local.json > REPO_PATH > .)"
        ),
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    app = create_app(repo_path=args.repo)
    print(f"  BdfDiff running on http://{args.host}:{args.port}")
    print(f"  Repository: {os.path.abspath(args.repo)}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
