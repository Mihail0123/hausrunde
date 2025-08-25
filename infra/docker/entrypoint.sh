#!/usr/bin/env sh
set -e

# Wait for the DB to be ready (using Python socket; no extra packages needed)
if [ -n "${DB_HOST}" ]; then
  echo "Waiting for DB at ${DB_HOST}:${DB_PORT:-3306}..."
  python - <<'PY'
import os, socket, time, sys
host = os.environ.get("DB_HOST")
port = int(os.environ.get("DB_PORT", "3306"))
if not host:
    sys.exit(0)
for _ in range(60):
    try:
        with socket.create_connection((host, port), timeout=1.0):
            print("DB is up")
            sys.exit(0)
    except Exception:
        time.sleep(1)
print("DB wait timeout", file=sys.stderr)
sys.exit(1)
PY
fi

echo "Applying migrations..."
python manage.py migrate --noinput

# Optional demo seeding (controlled via env toggles)
if [ "${DEMO_SEED:-0}" = "1" ]; then
  echo "Seeding demo data..."
  SEED_ARGS=""
  [ "${DEMO_SEED_WITH_REVIEWS:-0}" = "1" ] && SEED_ARGS="$SEED_ARGS --with-reviews"
  [ -n "${DEMO_SEED_ADS:-}" ] && SEED_ARGS="$SEED_ARGS --ads ${DEMO_SEED_ADS}"
  # Non-fatal if seeder fails (for example, command not present)
  python manage.py seed_demo --wipe-demo $SEED_ARGS || echo "Demo seeding failed (non-fatal)."
fi

# Ensure media directory exists
mkdir -p media

# Exec the main process (from Dockerfile CMD)
exec "$@"
