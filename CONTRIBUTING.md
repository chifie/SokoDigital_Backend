# Contributing to SokoDigital API

Thank you for considering contributing! This guide covers setup, coding standards, and the PR workflow.

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Database](#database)
- [Pull Request Process](#pull-request-process)

---

## Prerequisites

- **Python 3.12+**
- **PostgreSQL 16** (running locally or via Docker)
- **Redis 7** (optional, for rate limiting and caching)
- **Docker** (optional, for containerized development)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/sokodigital-backend.git
cd sokodigital-backend

# 2. Set up Python environment
python -m venv .venv
source .venv/bin/activate  # or: .venv\Scripts\activate on Windows

# 3. Install dependencies
make install-dev

# 4. Copy environment template
cp .env.example .env
# Edit .env with your local database credentials

# 5. Start PostgreSQL and Redis (optional, for local Docker)
make docker-up

# 6. Run migrations and seed data
make migrate
make seed

# 7. Start the development server
uvicorn app.main:app --reload --port 8000

# 8. Verify it works
curl http://localhost:8000/health
```

---

## Project Structure

```
sokodigital-backend/
├── app/
│   ├── api/v1/          # Route handlers (auth, products, orders, etc.)
│   ├── middleware/       # ASGI middleware (rate-limit, cache, metrics, etc.)
│   ├── models/          # SQLAlchemy ORM models
│   ├── schemas/         # Pydantic request/response schemas
│   ├── services/        # Business logic (email, auth, AI)
│   ├── tasks/           # ARQ background task handlers
│   ├── utils/           # Utilities (response wrapper, etc.)
│   ├── config.py        # Pydantic-settings configuration
│   ├── database.py      # Async SQLAlchemy engine & session
│   └── main.py          # FastAPI application factory
├── migrations/          # Alembic database migrations
├── tests/               # Pytest test suite
├── k8s/                 # Kubernetes manifests
├── scripts/             # Utility scripts
├── Dockerfile           # Multi-stage Docker build
├── docker-compose.yml   # Local development services
├── Makefile             # Common commands
└── requirements.txt     # Python dependencies
```

---

## Development Workflow

### Common Commands (via Makefile)

```bash
make install       # Install production dependencies
make install-dev   # Install dev dependencies (pytest, ruff, mypy)
make lint          # Run Ruff linter
make format        # Auto-format code with Ruff
make typecheck     # Run mypy type checker
make test          # Run unit tests (fast)
make test-all      # Run all tests (needs PostgreSQL)
make migrate       # Apply pending migrations
make migrate-autogen  # Auto-generate migration from model changes
make seed          # Apply seed data migration
make docker-up     # Start all services (db, redis, api, worker)
make docker-down   # Stop all services
make clean         # Remove caches and build artifacts
```

---

## Coding Standards

### Python Style Guide

- **Formatter**: [Ruff](https://docs.astral.sh/ruff/formatter/) (drop-in black-compatible)
- **Linter**: [Ruff](https://docs.astral.sh/ruff/) with rules from `pyproject.toml`
- **Type Hints**: Required for all public functions and methods. Use `| None` syntax (Python 3.10+).
- **Docstrings**: Google-style or reStructuredText for public APIs.

### Naming Conventions

| Kind               | Style           | Example                     |
|--------------------|-----------------|-----------------------------|
| Models             | `PascalCase`    | `class User(Base)`          |
| Schemas            | `PascalCase`    | `class UserResponse(BaseModel)` |
| Routes             | `snake_case`    | `async def list_products()` |
| Private helpers    | `_snake_case`   | `def _get_address_or_404()` |
| Constants          | `UPPER_CASE`    | `AUTH_RATE_LIMIT`           |
| Modules/files      | `snake_case`    | `rate_limit.py`             |

### OpenAPI Annotations

All endpoints must have:
- `summary=` — Short description shown in Swagger UI
- `docstring` — Longer description in the function body
- `response_model=` — Pydantic schema for the response
- `responses=` — Error responses (e.g. `{404: {"description": "Not found"}}`)
- `tags=` — Set via the router (e.g. `tags=["Products"]`)

### Error Handling

Always use `HTTPException` with appropriate status codes and descriptive messages.
The global exception handler wraps all errors into a consistent JSON envelope:

```json
{"success": false, "message": "...", "detail": "..."}
```

The `detail` key is preserved for backward compatibility.

---

## Testing

### Running Tests

```bash
make test           # Fast unit tests (no database needed)
make test-all       # Full test suite (requires PostgreSQL)
```

### Test Structure

- **`tests/test_pagination.py`** — Pure unit tests (no DB, no HTTP)
- **`tests/test_rate_limit.py`** — InMemoryRateLimiter logic
- **`tests/test_seller_follow.py`** — Follow/unfollow schema logic
- **`tests/test_error_handlers.py`** — Error response envelope format
- **`tests/test_background_tasks.py`** — ARQ task handlers (mocked Redis)
- **`tests/test_email_verification.py`** — Integration tests (requires PostgreSQL)

### Writing Tests

- Use `pytest` with `pytest-asyncio` for async tests
- Mock external services (Redis, SMTP) with `unittest.mock`
- Prefer `@pytest.mark.asyncio` decorator for async tests
- Use fixtures from `tests/conftest.py` for shared setup

---

## Database

### Migrations

This project uses **Alembic** for database migrations with async SQLAlchemy.

```bash
make migrate              # Apply pending migrations
make migrate-autogen      # Auto-generate from model changes
make migrate-show         # Show migration history
make migrate-down         # Roll back one migration
make seed                 # Apply seed data (admin user, categories, etc.)
```

### Seeding Data

Run `make seed` or `alembic upgrade a1b2c3d4e5f6` to insert sample data:

| User       | Email                   | Password    | Role     |
|------------|-------------------------|-------------|----------|
| Admin      | admin@sokodigital.com   | admin123    | admin    |
| Seller     | seller@sokodigital.com  | seller123   | seller   |
| Customer   | customer@example.com    | customer123 | customer |

### Full Reset

```bash
./scripts/reset_dev.sh
```

This drops the database, recreates it, runs all migrations, and seeds sample data.

---

## Pull Request Process

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/my-feature
   ```

2. **Make changes** following the coding standards above.

3. **Run checks locally**:
   ```bash
   make lint
   make typecheck
   make test        # Unit tests
   ```

4. **Commit with a descriptive message**:
   ```bash
   git commit -m "feat: add user profile avatars"
   ```
   We follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` — New feature
   - `fix:` — Bug fix
   - `chore:` — Maintenance
   - `docs:` — Documentation
   - `refactor:` — Code restructuring

5. **Push and open a PR** against `main`.

6. **Ensure CI passes** (lint → test → build).

7. **Request review** from at least one maintainer.

---

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async Guide](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [ARQ Background Tasks](https://arq-docs.helpmanual.io/)
- [Ruff Rules](https://docs.astral.sh/ruff/rules/)
