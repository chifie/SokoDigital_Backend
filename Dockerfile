# ── Builder stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime system dependencies (for psycopg2, curl for HEALTHCHECK)
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are useable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY app/ app/
COPY alembic.ini .
COPY migrations/ migrations/
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Create uploads directory
RUN mkdir -p /app/uploads

# Expose the port the app runs on
EXPOSE 8000

# Health check (uses curl which is faster than starting a Python process)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the entrypoint (runs migrations then starts uvicorn)
ENTRYPOINT ["./entrypoint.sh"]
