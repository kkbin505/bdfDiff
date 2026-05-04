"""
Flask View - routes and view logic.

Page routes all serve the JS SPA shell (index.html).
All data is delivered through /api/* JSON endpoints.
"""

from __future__ import annotations

import os
import tempfile

from flask import (
    Blueprint,
    Flask,
    jsonify,
    render_template,
    request,
)
from werkzeug.utils import secure_filename

from app.presenter.diff_presenter import DiffPresenter

UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), "bdfdiff_uploads")
ALLOWED_EXTENSIONS = {"bdf", "dat", "nas", "bulk"}

main = Blueprint("main", __name__)


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_presenter() -> DiffPresenter:
    from flask import current_app
    repo_path = current_app.config.get("REPO_PATH", ".")
    return DiffPresenter(repo_path=repo_path)


# ---------------------------------------------------------------------------
# SPA shell - all page routes serve the single-page app
# ---------------------------------------------------------------------------

@main.route("/")
@main.route("/<path:path>")
def spa(path: str = ""):
    """Serve the JS SPA for every non-API URL."""
    return render_template("index.html")


# ---------------------------------------------------------------------------
# JSON API endpoints
# ---------------------------------------------------------------------------

@main.route("/api/repo_info")
def api_repo_info():
    """Return repository info and recent commits."""
    presenter = _get_presenter()
    return jsonify({
        "repo_info": presenter.get_repo_info(),
        "commits": presenter.get_commits(max_count=30),
    })


@main.route("/api/commits")
def api_commits():
    """Return commit list, optionally filtered by file path."""
    filepath = request.args.get("filepath")
    presenter = _get_presenter()
    return jsonify(presenter.get_commits(filepath=filepath))


@main.route("/api/diff/upload", methods=["POST"])
def api_diff_upload():
    """Diff two uploaded BDF files and return JSON."""
    file_old = request.files.get("file_old")
    file_new = request.files.get("file_new")

    if not file_old or not file_new:
        return jsonify({"error": "Please upload both files."}), 400

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    old_name = secure_filename(file_old.filename or "old.bdf")
    new_name = secure_filename(file_new.filename or "new.bdf")
    old_path = os.path.join(UPLOAD_FOLDER, f"old_{old_name}")
    new_path = os.path.join(UPLOAD_FOLDER, f"new_{new_name}")
    file_old.save(old_path)
    file_new.save(new_path)

    presenter = _get_presenter()
    diff_data = presenter.diff_files(old_path, new_path)
    diff_data["mode"] = "upload"
    return jsonify(diff_data)


@main.route("/api/diff/text", methods=["POST"])
def api_diff_text():
    """Diff two BDF text strings and return JSON."""
    payload = request.get_json(force=True)
    old_text = payload.get("old_text", "")
    new_text = payload.get("new_text", "")
    presenter = _get_presenter()
    return jsonify(presenter.diff_texts(old_text, new_text))


@main.route("/api/diff/commits", methods=["POST"])
def api_diff_commits():
    """Diff a BDF file between two git commits and return JSON."""
    payload = request.get_json(force=True)
    filepath = payload.get("filepath", "")
    old_sha = payload.get("old_sha", "")
    new_sha = payload.get("new_sha", "")
    presenter = _get_presenter()
    return jsonify(presenter.diff_commits(filepath, old_sha, new_sha))


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(repo_path: str = ".") -> Flask:
    app = Flask(
        __name__,
        template_folder="view/templates",
        static_folder="view/static",
    )
    app.config["REPO_PATH"] = os.path.abspath(repo_path)
    app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB

    app.register_blueprint(main)
    return app
