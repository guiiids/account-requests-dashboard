"""
Gunicorn entry point for the AccountRequests Dashboard.
Usage: gunicorn -c gunicorn_config.py run:app
"""
import database
from app import app

# Initialise DB tables on startup (idempotent — uses CREATE TABLE IF NOT EXISTS)
database.init_db()
