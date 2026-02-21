"""
Gunicorn configuration for AccountRequests Dashboard.
Reads PORT / WEBSITES_PORT env vars so Azure App Service can control the port.
"""
import os

# Bind to the port Azure injects; fall back to 8000 (matches EXPOSE in Dockerfile)
_port = os.environ.get("PORT") or os.environ.get("WEBSITES_PORT") or "8000"
bind = f"0.0.0.0:{_port}"

# Workers: 2x CPU + 1 is the standard Gunicorn recommendation for I/O-bound apps
workers = int(os.environ.get("GUNICORN_WORKERS", 3))
threads = int(os.environ.get("GUNICORN_THREADS", 2))

# Timeouts
timeout = 120
keepalive = 5

# Logging — send access + error logs to stdout so Azure Log Stream picks them up
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
