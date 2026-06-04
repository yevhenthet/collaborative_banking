# Question Bank

A web-based tool for medical departments to collaboratively build, peer-review, and draw exam question banks aligned to learning outcomes.

**UI language:** Ukrainian / English toggle per session  
**Stack:** FastAPI · Jinja2 · SQLAlchemy · SQLite  
**Access model:** Two roles — `teacher` (add & vote on questions) and `admin` (full control)

---

## Features

- **Curriculum structure** — Faculties → Disciplines → Modules → Topics → ILOs (Bloom level tagged)
- **Question lifecycle** — `pending` → peer-review voting → `active` → `retired`; full revision history
- **Peer review** — 5 behaviorally-anchored quality criteria; quorum + approval thresholds configured by admin; blind voting (reviewer names hidden from teachers until activation)
- **Blueprint-based test generation** — stratified draw by topic weight × difficulty (Basic / Moderate / High); up to 3 parallel variants; exposure-control to avoid repeating recent questions
- **Item analysis** — facility index (p), discrimination index (Ebel D), KR-20 reliability, Wilson 95% CI; auto-flags mismatched difficulty declarations
- **Formative quizzes** — one question per ILO; LO coverage matrix on every test
- **Export** — DOCX and PDF with org branding, pass threshold, and model answers
- **JSON import/export** — per-topic bulk transfer of questions + ILOs between installations

---

## Requirements

- Python 3.10 or newer
- `make` (standard on macOS/Linux; on Windows use Git Bash or WSL)

No external database server required — SQLite is used out of the box.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/yevhenthet/collaborative_banking.git
cd collaborative_banking

# 2. Install dependencies into a virtual environment
make install

# 3. Generate a .env file with a fresh secret key
make setup

# 4. Create the first admin account
make admin

# 5. Start the server
make run
```

Open **http://127.0.0.1:8000** in your browser and log in with the admin account you just created.

---

## All make targets

| Command | Description |
|---|---|
| `make install` | Create `venv/` and install all Python dependencies |
| `make setup` | Generate `.env` with a random `SESSION_SECRET_KEY` (skips if already exists) |
| `make admin` | Interactive prompt to create the first admin user |
| `make run` | Start the server at http://127.0.0.1:8000 |
| `make dev` | Start with auto-reload for development |
| `make clean` | Remove `__pycache__` and `.pyc` files |
| `make reset` | **Irreversible** — delete the database |

---

## Configuration

All configuration lives in `.env` (created by `make setup`). It is git-ignored and never committed.

| Variable | Required | Description |
|---|---|---|
| `SESSION_SECRET_KEY` | Yes | 64-char hex string; sign sessions. Change invalidates all active sessions. |
| `DATABASE_URL` | No | SQLite path (default: `sqlite:///./question_bank.db`) |
| `HOST` | No | Bind address (default: `127.0.0.1`) |
| `PORT` | No | Port (default: `8000`) |

See `.env.example` for a documented template.

---

## First steps after login

1. **Admin → Settings** — set your institution name and department; configure voting thresholds (quorum, approval %, pass threshold).
2. **Admin → Teachers** — add teacher accounts.
3. **Home → Add Faculty** — build your curriculum hierarchy: Faculty → Discipline → Module → Topic.
4. **Topic page** — add ILOs (with Bloom level), then let teachers submit questions.
5. **Vote queue** — teachers peer-review each other's questions; questions auto-activate when quorum + approval thresholds are met.
6. **Module → Generate Test** — draw a blueprint-balanced exam once enough questions are active.

---

## Data portability

**Export** a topic's questions + ILOs as JSON from the Topic page.  
**Import** a JSON file on any other installation's Topic page to transfer content between departments or institutions.

---

## Production notes

This tool is designed for **local / intranet deployment** within a department.

- Keep the server behind a reverse proxy (nginx, Caddy) if exposing beyond localhost.
- Set a strong `SESSION_SECRET_KEY` in `.env` and do not share it.
- Back up `question_bank.db` regularly — it is the only persistent state.
- The database migrates automatically on each startup; no manual migration step is needed.

---

## Project structure

```
question-bank/
├── app/
│   ├── main.py          # FastAPI app, session middleware, auto-migrations
│   ├── models.py        # SQLAlchemy ORM models
│   ├── database.py      # Engine + session factory
│   ├── auth.py          # Password hashing, session helpers
│   ├── config.py        # Settings schema + org settings
│   ├── draw.py          # Blueprint draw, quiz draw, exposure control
│   ├── item_analysis.py # Facility, discrimination, KR-20, review profile
│   ├── export.py        # DOCX + PDF generation
│   ├── i18n.py          # UI strings (UK / EN), CRIT_ANCHORS
│   ├── templates.py     # Jinja2 environment
│   └── routers/         # Route handlers
├── templates/           # Jinja2 HTML templates
├── static/              # CSS
├── run.py               # Entry point (loads .env → starts uvicorn)
├── seed_admin.py        # One-time admin creation script
├── requirements.txt
├── Makefile
├── .env.example
└── INVENTORY.md         # Full feature inventory (developer reference)
```

---

## License

MIT — free to use, modify, and distribute with attribution.
