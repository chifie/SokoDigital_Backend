#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  SokoDigital — Reset Development Environment
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Drops the database, recreates it, runs all migrations, and seeds sample data.
#  Safe to run multiple times — idempotent.
#
#  Usage:
#    ./scripts/reset_dev.sh              # uses .env or defaults
#    DATABASE_URL="..." ./scripts/reset_dev.sh  # override connection
#
#  Prerequisites:
#    - PostgreSQL running locally (or via `docker compose up -d db`)
#    - Python virtual environment with deps installed
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Load configuration ──────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load .env if present
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
    log_info "Loaded .env from $PROJECT_ROOT/.env"
fi

# Default connection parameters (overridable via env vars)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
DB_NAME="${DB_NAME:-sokodigital_db}"

# Full DATABASE_URL override takes precedence
if [ -n "${DATABASE_URL:-}" ]; then
    log_info "Using DATABASE_URL from environment"
    # Parse URL for psql connection
    DB_USER="$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')"
    DB_PASSWORD="$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')"
    DB_HOST="$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')"
    DB_PORT="$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')"
    DB_NAME="$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')"
fi

export PGPASSWORD="$DB_PASSWORD"

# ── Step 1: Drop & recreate database ────────────────────────────────────────

log_info "Step 1/4: Dropping database \"$DB_NAME\"..."

if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pg_stat_activity.pid)
     FROM pg_stat_activity
     WHERE pg_stat_activity.datname = '$DB_NAME'
       AND pid <> pg_backend_pid();" 2>/dev/null; then
    log_ok "Terminated connections to \"$DB_NAME\""
fi

if dropdb --if-exists -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME" 2>/dev/null; then
    log_ok "Dropped database \"$DB_NAME\""
else
    log_warn "Could not drop database (may not exist yet)"
fi

log_info "Creating database \"$DB_NAME\"..."
createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"
log_ok "Created database \"$DB_NAME\""

# ── Step 2: Run migrations ──────────────────────────────────────────────────

cd "$PROJECT_ROOT"

log_info "Step 2/4: Running database migrations..."
if alembic upgrade head 2>&1; then
    log_ok "Migrations applied"
else
    log_error "Migration failed. See output above."
    exit 1
fi

# ── Step 3: Seed data ───────────────────────────────────────────────────────

log_info "Step 3/4: Seeding sample data..."
if alembic upgrade a1b2c3d4e5f6 2>&1; then
    log_ok "Seed data applied"
else
    log_warn "Seed data may already exist or migration failed (idempotent, safe to ignore)"
fi

# ── Step 4: Verify ──────────────────────────────────────────────────────────

log_info "Step 4/4: Verifying setup..."

# Count tables
TABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
log_ok "$TABLE_COUNT tables in database"

# Check seed users
USER_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT count(*) FROM users;" | tr -d ' ')
log_ok "$USER_COUNT users seeded"

# Check categories
CAT_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT count(*) FROM categories;" | tr -d ' ')
log_ok "$CAT_COUNT categories seeded"

# Check products
PROD_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT count(*) FROM products;" | tr -d ' ')
log_ok "$PROD_COUNT products seeded"

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Development environment reset complete!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  API:       http://localhost:8000"
echo "  Docs:      http://localhost:8000/docs"
echo ""
echo "  Admin:     admin@sokodigital.com / admin123"
echo "  Seller:    seller@sokodigital.com / seller123"
echo "  Customer:  customer@example.com / customer123"
echo ""
