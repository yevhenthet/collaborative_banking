import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .database import engine, Base
from .routers import auth, disciplines, questions, tests, admin, help

Base.metadata.create_all(bind=engine)

_MIGRATIONS = [
    "ALTER TABLE topics ADD COLUMN is_high_stakes BOOLEAN NOT NULL DEFAULT 0",
    "ALTER TABLE topics ADD COLUMN hours_weight INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE questions ADD COLUMN model_answer TEXT",
    "ALTER TABLE questions ADD COLUMN question_type VARCHAR(20)",
    "ALTER TABLE questions ADD COLUMN learning_objective VARCHAR(300)",
    "ALTER TABLE questions ADD COLUMN current_round INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE votes ADD COLUMN round INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE tests ADD COLUMN batch_id INTEGER",
    "ALTER TABLE tests ADD COLUMN variant_label VARCHAR(10)",
    "CREATE TABLE IF NOT EXISTS test_results (id INTEGER PRIMARY KEY, test_id INTEGER NOT NULL REFERENCES tests(id), question_id INTEGER NOT NULL REFERENCES questions(id), correct_count INTEGER NOT NULL, total_students INTEGER NOT NULL, recorded_at DATETIME)",
    "CREATE TABLE IF NOT EXISTS topic_learning_outcomes (id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE, text VARCHAR(500) NOT NULL)",
    "ALTER TABLE votes ADD COLUMN crit_wording INTEGER",
    "ALTER TABLE votes ADD COLUMN crit_lo INTEGER",
    "ALTER TABLE votes ADD COLUMN crit_bloom INTEGER",
    "ALTER TABLE votes ADD COLUMN crit_answer INTEGER",
    "ALTER TABLE questions ADD COLUMN learning_outcome_id INTEGER REFERENCES topic_learning_outcomes(id)",
    "ALTER TABLE tests ADD COLUMN topic_id INTEGER REFERENCES topics(id)",
    "ALTER TABLE tests ADD COLUMN is_quiz BOOLEAN NOT NULL DEFAULT 0",
    "ALTER TABLE topic_learning_outcomes ADD COLUMN bloom_level VARCHAR(1)",
    "ALTER TABLE votes ADD COLUMN crit_accuracy INTEGER",
    "UPDATE questions SET proposed_difficulty='M' WHERE proposed_difficulty='S'",
    "UPDATE questions SET proposed_difficulty='H' WHERE proposed_difficulty='V'",
    "UPDATE questions SET final_difficulty='M' WHERE final_difficulty='S'",
    "UPDATE questions SET final_difficulty='H' WHERE final_difficulty='V'",
    "UPDATE votes SET difficulty_vote='M' WHERE difficulty_vote='S'",
    "UPDATE votes SET difficulty_vote='H' WHERE difficulty_vote='V'",
    "UPDATE topic_learning_outcomes SET bloom_level='M' WHERE bloom_level='S'",
    "UPDATE topic_learning_outcomes SET bloom_level='H' WHERE bloom_level='V'",
    "ALTER TABLE test_results ADD COLUMN upper_correct INTEGER",
    "ALTER TABLE test_results ADD COLUMN lower_correct INTEGER",
    "ALTER TABLE tests ADD COLUMN result_mean REAL",
    "ALTER TABLE tests ADD COLUMN result_sd REAL",
    "CREATE TABLE IF NOT EXISTS question_revisions (id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE, round INTEGER NOT NULL, text TEXT NOT NULL, model_answer TEXT, proposed_difficulty VARCHAR(1) NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)",
    # Vote round summaries
    "CREATE TABLE IF NOT EXISTS vote_round_summaries (id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE, round INTEGER NOT NULL, outcome VARCHAR(20) NOT NULL, n_votes INTEGER NOT NULL, approval_pct REAL, mean_wording REAL, mean_lo REAL, mean_bloom REAL, mean_answer REAL, mean_accuracy REAL, sd_wording REAL, sd_lo REAL, sd_bloom REAL, sd_answer REAL, sd_accuracy REAL, diff_consensus_pct REAL, closed_at DATETIME DEFAULT CURRENT_TIMESTAMP)",
    # Cached empirical metrics on Question
    "ALTER TABLE questions ADD COLUMN cached_p REAL",
    "ALTER TABLE questions ADD COLUMN cached_n_tested INTEGER",
    "ALTER TABLE questions ADD COLUMN cached_d REAL",
    "ALTER TABLE questions ADD COLUMN cached_rec VARCHAR(10)",
    # Computed metrics on Test
    "ALTER TABLE tests ADD COLUMN kr20 REAL",
    "ALTER TABLE tests ADD COLUMN exp_pass_rate REAL",
]

with engine.connect() as conn:
    for sql in _MIGRATIONS:
        try:
            conn.execute(text(sql))
            conn.commit()
        except OperationalError:
            # Expected: column/table already exists from prior startup
            pass
        except Exception as exc:
            # Unexpected — DML failures or corruption should surface
            import warnings
            warnings.warn(f"Migration failed unexpectedly: {sql!r} — {exc}")

_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "")
if not _SECRET_KEY:
    import secrets as _sec
    _SECRET_KEY = _sec.token_hex(32)
    import warnings as _w
    _w.warn(
        "SESSION_SECRET_KEY env var not set — using a random key. "
        "Sessions will not survive restart. Set SESSION_SECRET_KEY in production.",
        stacklevel=1,
    )

app = FastAPI(title="Question Bank")
app.add_middleware(
    SessionMiddleware,
    secret_key=_SECRET_KEY,
    same_site="strict",
    https_only=os.environ.get("HTTPS_ONLY", "false").lower() == "true",
)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(disciplines.router)
app.include_router(questions.router)
app.include_router(tests.router)
app.include_router(admin.router)
app.include_router(help.router)
