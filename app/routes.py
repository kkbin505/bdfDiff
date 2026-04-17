"""
Flask View – routes and view logic.
"""

from __future__ import annotations

import os
import tempfile

from flask import (
    Blueprint,
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
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
# Routes
# ---------------------------------------------------------------------------

@main.route("/")
def index():
    presenter = _get_presenter()
    repo_info = presenter.get_repo_info()
    commits = presenter.get_commits(max_count=30)
    return render_template("index.html", repo_info=repo_info, commits=commits)


@main.route("/diff/upload", methods=["GET", "POST"])
def diff_upload():
    """Diff two uploaded BDF files."""
    presenter = _get_presenter()
    if request.method == "POST":
        file_old = request.files.get("file_old")
        file_new = request.files.get("file_new")

        if not file_old or not file_new:
            return render_template(
                "diff.html",
                error="Please upload both files.",
                presenter=presenter,
            )

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        old_name = secure_filename(file_old.filename or "old.bdf")
        new_name = secure_filename(file_new.filename or "new.bdf")
        old_path = os.path.join(UPLOAD_FOLDER, f"old_{old_name}")
        new_path = os.path.join(UPLOAD_FOLDER, f"new_{new_name}")
        file_old.save(old_path)
        file_new.save(new_path)

        diff_data = presenter.diff_files(old_path, new_path)
        diff_data["mode"] = "upload"
        return render_template("diff.html", data=diff_data)

    return render_template("diff_upload.html")


@main.route("/diff/text", methods=["POST"])
def diff_text():
    """Diff two BDF texts pasted in a form."""
    old_text = request.form.get("old_text", "")
    new_text = request.form.get("new_text", "")
    presenter = _get_presenter()
    diff_data = presenter.diff_texts(old_text, new_text)
    diff_data["mode"] = "text"
    return render_template("diff.html", data=diff_data)


@main.route("/diff/commits", methods=["GET", "POST"])
def diff_commits():
    """Diff a BDF file between two git commits."""
    presenter = _get_presenter()
    repo_info = presenter.get_repo_info()

    if request.method == "POST":
        filepath = request.form.get("filepath", "")
        old_sha = request.form.get("old_sha", "")
        new_sha = request.form.get("new_sha", "")

        if not (filepath and old_sha and new_sha):
            return render_template(
                "diff_commits.html",
                repo_info=repo_info,
                commits=presenter.get_commits(),
                error="Please fill all fields.",
            )

        if old_sha == new_sha:
            return render_template(
                "diff_commits.html",
                repo_info=repo_info,
                commits=presenter.get_commits(filepath=filepath),
                error="Old commit and new commit cannot be the same.",
            )

        diff_data = presenter.diff_commits(filepath, old_sha, new_sha)
        if (
            not diff_data.get("summary", {}).get("total_changes", 0)
            and not diff_data.get("old_summary")
            and not diff_data.get("new_summary")
        ):
            return render_template(
                "diff_commits.html",
                repo_info=repo_info,
                commits=presenter.get_commits(filepath=filepath),
                error="Unable to load file content from one or both commits. Please check the selected file and commits.",
            )

        diff_data["mode"] = "git"
        return render_template("diff.html", data=diff_data)

    commits = presenter.get_commits(max_count=50)
    return render_template(
        "diff_commits.html", repo_info=repo_info, commits=commits
    )


@main.route("/grid_visualization")
def grid_visualization():
    presenter = _get_presenter()
    data = presenter.get_diff_data()
    return render_template("grid_visualization.html", data=data)


# API endpoints -----------------------------------------------------------

@main.route("/api/commits")
def api_commits():
    filepath = request.args.get("filepath")
    presenter = _get_presenter()
    return jsonify(presenter.get_commits(filepath=filepath))


@main.route("/api/diff/text", methods=["POST"])
def api_diff_text():
    payload = request.get_json(force=True)
    old_text = payload.get("old_text", "")
    new_text = payload.get("new_text", "")
    presenter = _get_presenter()
    return jsonify(presenter.diff_texts(old_text, new_text))


@main.route("/api/diff/commits", methods=["POST"])
def api_diff_commits():
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
