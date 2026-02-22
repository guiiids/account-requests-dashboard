# Audit Trail System — Delivery Package

This package contains all files changed or created to implement the support-agent audit trail system in the `account-requests-dashboard` application.

## Files Included

| File | Type | Description |
| :--- | :--- | :--- |
| `audit.py` | **New** | Core audit module. Contains `log_audit_event()` and query helpers. Drop into the project root. |
| `database.py` | **Updated** | Adds `audit_log` table creation to `init_db()` and `migrate_db()`. Safe to run on existing databases. |
| `app.py` | **Updated** | All agent action routes now call `audit.log_audit_event()`. New `/other/audit` viewer route added. |
| `audit_log.html` | **New** | Jinja2 template for the cross-request audit log viewer page. Place in `templates/`. |
| `base.html` | **Updated** | Sidebar navigation updated to include an **Audit Log** link. |

## Installation

1. Copy `audit.py` to the project root (alongside `app.py`).
2. Replace `app.py`, `database.py`, and `templates/base.html` with the updated versions.
3. Copy `audit_log.html` into the `templates/` directory.
4. Restart the application. On first start, `init_db()` / `migrate_db()` will automatically create the `audit_log` table and its indexes in the existing SQLite database — no manual SQL required.

## New Endpoint

| Method | URL | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/other/audit` | Staff only | Cross-request audit log viewer with agent and action-category filters. |

## Audited Events

| Event | Trigger |
| :--- | :--- |
| `agent.login.success` | Successful staff login |
| `agent.login.failed` | Failed login attempt (wrong email) |
| `agent.logout` | Staff logout |
| `request.status.update` | Status changed (captures before/after values) |
| `request.assignment.update` | Request assigned (captures before/after assignee) |
| `request.comment.create` | Internal note added |
| `request.email.send` | Outbound email sent to requester |
| `request.import.create` | Request manually imported |
| `request.view` | Request detail tab opened by an agent |
