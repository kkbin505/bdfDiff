# BdfDiff – Nastran BDF Visual Diff Tool

A Python MVP (Model–View–Presenter) web application for visually comparing
two [Nastran BDF](https://nastran.readthedocs.io/) files and managing model
versions with Git.

---

## Features

| Feature | Description |
|---|---|
| **Card-level diff** | Detects added / removed / modified bulk-data cards (GRID, CQUAD4, MAT1, PSHELL, …) |
| **Side-by-side view** | Line-by-line colour-coded comparison |
| **Unified diff** | Classic `git diff`-style output with syntax highlighting |
| **Git integration** | Browse commit history, diff a BDF file between any two commits |
| **Upload & paste** | Compare files directly without Git |
| **Keyword filter** | Filter diff results by card type (e.g. show only GRID changes) |
| **REST API** | JSON API for programmatic access |

---

## Architecture – MVP pattern

```
bdfDiff/
├── app/
│   ├── model/
│   │   ├── bdf_parser.py     # Parse BDF files into structured card objects
│   │   ├── git_manager.py    # Git repository operations (via GitPython)
│   │   └── diff_engine.py    # Card-level + text-level diff computation
│   ├── presenter/
│   │   └── diff_presenter.py # Business logic – orchestrates Model → View data
│   ├── view/
│   │   ├── templates/        # Jinja2 HTML templates
│   │   └── static/           # CSS & JavaScript
│   └── routes.py             # Flask routes (View entry-points)
├── tests/
│   ├── sample_files/         # sample_v1.bdf / sample_v2.bdf for testing
│   ├── test_bdf_parser.py
│   ├── test_diff_engine.py
│   └── test_presenter.py
├── config.py
├── requirements.txt
└── run.py                    # CLI entry point
```

---

## Quick start

```bash
# 1. Clone & install
git clone https://github.com/kkbin505/bdfDiff.git
cd bdfDiff
pip install -r requirements.txt

# 2. Run inside a Git repo that contains BDF files
python run.py --repo /path/to/your/nastran/project

# 3. Open http://127.0.0.1:5000 in your browser
```

### Options

```
python run.py --help

  --repo PATH     Git repository path (default: .)
  --host HOST     Bind address (default: 127.0.0.1)
  --port PORT     Port number (default: 5000)
  --debug         Enable Flask debug / auto-reload mode
```

---

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/diff/text` | Diff two BDF text strings |
| `POST` | `/api/diff/commits` | Diff a file between two Git commits |
| `GET` | `/api/commits?filepath=model.bdf` | List commits for a file |

**Example – diff two text strings:**

```bash
curl -X POST http://localhost:5000/api/diff/text \
     -H "Content-Type: application/json" \
     -d '{"old_text": "GRID    1   ...", "new_text": "GRID    1   ..."}'
```

**Response structure:**

```json
{
  "summary": {"added": 3, "removed": 0, "modified": 2, "unchanged": 10, "total_changes": 5},
  "keyword_stats": {"GRID": {"added": 2}, "PSHELL": {"modified": 1}},
  "card_diffs": [...],
  "text_diff": [...],
  "side_by_side": [...]
}
```

---

## Running tests

```bash
pytest tests/ -v
```

---

## Workflow example with Git

```bash
# Track BDF files in Git
git init my-fem-project && cd my-fem-project
cp /path/to/model_v1.bdf model.bdf
git add model.bdf && git commit -m "Initial model"

# Make changes, commit a new version
cp /path/to/model_v2.bdf model.bdf
git add model.bdf && git commit -m "Updated thickness and mesh"

# Start BdfDiff in the repo
python /path/to/bdfDiff/run.py --repo .

# Open http://127.0.0.1:5000 → Git Diff → select the two commits
```

---

## Supported BDF formats

- Small-field (8-character columns)
- Free-field (comma-separated)
- Large-field (`*`-prefixed 16-character columns)
- Continuation lines (`+` prefix)

Sections handled: Executive Control, Case Control, Bulk Data.

---

## License

MIT
