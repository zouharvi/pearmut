# Pearmut - Platform for Evaluation and Reviewing of Multilingual Tasks

Python-based annotation platform for translation/NLP evaluation with web UI.

## Structure

- `server/` - Python backend (FastAPI)
  - `app.py` - FastAPI server
  - `cli.py` - CLI commands
  - `assignment.py` - Campaign assignment logic
  - `tests/` - Python tests
- `web/` - TypeScript/HTML frontend
  - Built with webpack to `server/static/`
- `examples/` - Sample campaign JSON configs

## Build & Test

**Setup:**
```bash
pip install -e .
cd web && npm install
```

**Lint (required before commit):**
```bash
ruff check server
ruff check --select=I server
```

**Test:**
```bash
pytest server/tests/*
```

**Build web:**
```bash
cd web && npm run build
```

**Run locally:**
```bash
pearmut add examples/*.json
pearmut run
```

## Requirements

- Python ≥3.12
- Node.js 18
- Always run `ruff check` before committing Python changes
- Web builds must succeed before committing frontend changes
- Tests in `server/tests/` must pass

## Style Guide

- Write minimal, elegant code—no unnecessary fluff
- Prioritize maintainability and readability
- Keep functions focused and concise
- Avoid over-engineering solutions

## Key Facts

- Backend in Python with FastAPI, frontend in TypeScript
- Configuration via JSON campaign files
- CI runs ruff, pytest, and npm build on all PRs
- Package published to PyPI as `pearmut`
