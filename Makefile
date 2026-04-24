PYTHON  := python3
PIP     := $(PYTHON) -m pip
UVICORN := uvicorn
STREAMLIT := streamlit

.PHONY: install test test-cov api frontend run lint clean

install:
	$(PIP) install -r requirements.txt

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	$(PYTHON) -m pytest tests/ -v

test-cov:
	$(PYTHON) -m pytest tests/ --cov=app --cov-report=term-missing --cov-report=html

# ── Run ───────────────────────────────────────────────────────────────────────
api:
	$(UVICORN) app.main:app --reload --port 8000

frontend:
	$(STREAMLIT) run frontend/app.py --server.port 8501

# Runs both in background; kill with 'make stop'
run:
	@echo "Starting API on :8000 and frontend on :8501"
	$(UVICORN) app.main:app --port 8000 &
	$(STREAMLIT) run frontend/app.py --server.port 8501

stop:
	@pkill -f "uvicorn app.main" || true
	@pkill -f "streamlit run" || true

# ── Quality ───────────────────────────────────────────────────────────────────
lint:
	$(PYTHON) -m ruff check app/ tests/ || true

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage
