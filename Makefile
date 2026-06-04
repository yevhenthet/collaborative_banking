.PHONY: help install setup admin run dev clean reset

PYTHON  := python3
VENV    := venv
PIP     := $(VENV)/bin/pip
PYBIN   := $(VENV)/bin/python

help:
	@echo "Question Bank — available targets:"
	@echo "  make install   Create venv and install dependencies"
	@echo "  make setup     Generate .env with a fresh secret key"
	@echo "  make admin     Create the first admin user"
	@echo "  make run       Start the server  (http://127.0.0.1:8000)"
	@echo "  make dev       Start with auto-reload (development)"
	@echo "  make clean     Remove .pyc files and __pycache__"
	@echo "  make reset     Delete the database (⚠ irreversible)"

install:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip -q
	$(PIP) install -r requirements.txt
	@echo "✓  Dependencies installed. Run 'make setup' next."

setup:
	@if [ ! -f .env ]; then \
		SECRET=$$($(PYTHON) -c 'import secrets; print(secrets.token_hex(32))'); \
		echo "SESSION_SECRET_KEY=$$SECRET" > .env; \
		echo "✓  .env created with a fresh secret key."; \
	else \
		echo ".env already exists — skipping key generation."; \
	fi

admin: setup
	$(PYBIN) seed_admin.py

run: setup
	$(PYBIN) run.py

dev: setup
	$(VENV)/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓  Cache cleared."

reset:
	@echo "WARNING: this will delete the database and all data."
	@read -p "Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ] || exit 1
	rm -f question_bank.db qbank.db
	@echo "✓  Database deleted."
