"""
Audit Trail Module — Account Requests Dashboard
================================================
Provides a centralized, structured, append-only audit log for all
support-agent actions.  Every call to ``log_audit_event`` writes one
immutable row to the ``audit_log`` table.

Usage
-----
    from audit import log_audit_event

    log_audit_event(
        actor_email = "nadia.clark@agilent.com",
        action      = "request.status.update",
        target_id   = "ACCT-0001",
        details     = {"from": "Open", "to": "In Progress"},
        success     = True,
    )

The function is safe to call from any Flask request context (it reads
``request.remote_addr`` automatically) and also from outside a request
context (e.g. CLI scripts), in which case ``actor_ip`` is left NULL.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

import database

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def log_audit_event(
    actor_email: str,
    action: str,
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict | None = None,
    success: bool = True,
    actor_ip: str | None = None,
) -> None:
    """
    Write one audit record to the ``audit_log`` table.

    Parameters
    ----------
    actor_email : str
        Email address of the support agent performing the action.
    action : str
        Dot-separated event name, e.g. ``"request.status.update"``.
    target_type : str, optional
        Kind of object being acted upon, e.g. ``"request"`` or ``"system"``.
    target_id : str, optional
        Identifier of the target object, e.g. ``"ACCT-0001"``.
    details : dict, optional
        Arbitrary machine-readable context for the event.  Will be
        serialised to JSON.
    success : bool
        Whether the action completed successfully.  Defaults to ``True``.
    actor_ip : str, optional
        Override the IP address.  When ``None`` (the default) the function
        tries to read it from the current Flask request context.
    """
    # Resolve IP address from Flask request context when not supplied.
    if actor_ip is None:
        actor_ip = _get_request_ip()

    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    details_json = json.dumps(details or {})

    try:
        conn = database.get_connection()
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO audit_log (
                event_id, timestamp, actor_email, actor_ip,
                action, target_type, target_id, details, success
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                timestamp,
                actor_email.lower().strip(),
                actor_ip,
                action,
                target_type,
                target_id,
                details_json,
                1 if success else 0,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:  # pragma: no cover
        # Audit failures must NEVER crash the application.
        logger.error("audit_log write failed for action=%s actor=%s: %s", action, actor_email, exc)


# ---------------------------------------------------------------------------
# Query helpers (used by the audit viewer route)
# ---------------------------------------------------------------------------

def get_audit_log(
    actor_email: str | None = None,
    target_id: str | None = None,
    action_prefix: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """
    Return audit log entries, newest first, with optional filters.

    Parameters
    ----------
    actor_email : str, optional
        Filter to a specific agent.
    target_id : str, optional
        Filter to a specific request key (e.g. ``"ACCT-0001"``).
    action_prefix : str, optional
        Filter by the start of the action name (e.g. ``"agent."``).
    limit : int
        Maximum number of rows to return.  Defaults to 200.
    """
    conn = database.get_connection()
    c = conn.cursor()

    query = "SELECT * FROM audit_log WHERE 1=1"
    params: list = []

    if actor_email:
        query += " AND actor_email = ?"
        params.append(actor_email.lower().strip())

    if target_id:
        query += " AND target_id = ?"
        params.append(target_id.upper().strip())

    if action_prefix:
        query += " AND action LIKE ?"
        params.append(action_prefix + "%")

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    entries = []
    for row in rows:
        entry = dict(row)
        # Parse the JSON details field back into a dict for convenience.
        try:
            entry["details"] = json.loads(entry.get("details") or "{}")
        except (json.JSONDecodeError, TypeError):
            entry["details"] = {}
        entries.append(entry)

    return entries


def get_audit_log_for_request(request_key: str) -> list[dict]:
    """Shorthand: return all audit entries for a single request."""
    return get_audit_log(target_id=request_key, limit=500)


def get_audit_log_for_agent(actor_email: str, limit: int = 100) -> list[dict]:
    """Shorthand: return the most recent audit entries for one agent."""
    return get_audit_log(actor_email=actor_email, limit=limit)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_request_ip() -> str | None:
    """
    Safely extract the client IP from the current Flask request context.
    Returns ``None`` when called outside a request context.
    """
    try:
        from flask import request as flask_request
        # Respect X-Forwarded-For when behind a proxy (Azure App Service).
        forwarded_for = flask_request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return flask_request.remote_addr
    except RuntimeError:
        # No active Flask request context.
        return None
