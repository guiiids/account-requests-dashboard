#!/bin/sh
# startup.sh — called by Docker CMD: ["./startup.sh","gunicorn","-c","gunicorn_config.py","run:app"]
# Any args passed by CMD are forwarded directly, e.g. `gunicorn -c gunicorn_config.py run:app`
set -e
echo "▶  Starting AccountRequests Dashboard..."
exec "$@"
