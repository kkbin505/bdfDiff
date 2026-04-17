"""
BdfDiff – Application entry point.

Usage:
    python run.py [--repo PATH] [--host HOST] [--port PORT] [--debug]

The --repo flag sets the Git repository path that BdfDiff will use for
commit-history features. Defaults to the current working directory.
"""

import argparse
import os
import sys

# Allow running from the project root without installing the package.
sys.path.insert(0, os.path.dirname(__file__))

from app.routes import create_app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BdfDiff – Nastran BDF visual diff tool"
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Path to the Git repository containing BDF files (default: .)",
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
