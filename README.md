# Account Requests Dashboard

> **Internal tool for Agilent staff** — Centralized management of iLab account signup requests, replacing manual email-based tracking with a professional, real-time dashboard.

![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue) ![Flask 3.x](https://img.shields.io/badge/flask-3.x-green) ![Docker](https://img.shields.io/badge/docker-multi--stage-lightblue) ![Azure App Service](https://img.shields.io/badge/deploy-Azure%20App%20Service-0078D4)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development](#local-development)
  - [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [API Reference](#api-reference)
  - [Webhook (Power Automate)](#webhook-power-automate)
  - [Request Management](#request-management)
  - [User Management](#user-management)
- [Authentication & Authorization](#authentication--authorization)
- [Audit Trail](#audit-trail)
- [Notification System](#notification-system)
- [Deployment](#deployment)
  - [Docker](#docker)
  - [Azure App Service](#azure-app-service)
- [UI / Design System](#ui--design-system)
- [Contributing](#contributing)

---

## Overview

The **Account Requests Dashboard** is an internal staff tool that processes iLab account signup requests for the Agilent iLab Support team. Rather than tracking requests across scattered email threads and spreadsheets, agents use a single dashboard to triage, respond, and close requests.

**How it works:**

1. A new user requests an account on [iLab Solutions](https://my.ilabsolutions.com).
2. iLab sends a notification email to a shared Agilent mailbox.
3. **Power Automate** picks up the email and POSTs it to the dashboard's webhook endpoint.
4. The dashboard parses the email, creates a structured request record (`ACCT-0001`), and makes it available for agents to triage.
5. Replies to the original email thread are **automatically threaded** into the same request via Outlook Conversation IDs.

> 📖 _See also:_ [Email Parser Deep Dive](docs/email_parser.md) · [Power Automate Integration](docs/power_automate.md)

---

## Architecture

```
┌──────────────┐     ┌────────────────────┐     ┌─────────────────────────┐
│  iLab Email  │────▶│  Power Automate    │────▶│  Webhook Endpoint       │
│  (Mailbox)   │     │  (O365 Flow)       │     │  POST /api/webhook/     │
└──────────────┘     └────────────────────┘     │  new-request            │
                                                 └───────────┬─────────────┘
                                                             │
                                                             ▼
                     ┌────────────────────────────────────────────────────┐
                     │              Flask Application (app.py)           │
                     │  ┌──────────┐  ┌───────────┐  ┌───────────────┐  │
                     │  │ email_   │  │ database  │  │ notification_ │  │
                     │  │ parser   │  │ (SQLite)  │  │ util          │  │
                     │  └──────────┘  └───────────┘  └───────────────┘  │
                     │  ┌──────────┐                                    │
                     │  │ audit    │   Gunicorn (run.py)                │
                     │  └──────────┘                                    │
                     └────────────────────────────────────────────────────┘
                                                             │
                                                             ▼
                     ┌────────────────────────────────────────────────────┐
                     │             Docker / Azure App Service             │
                     └────────────────────────────────────────────────────┘
```

> 📖 _See also:_ [Architecture Deep Dive](docs/architecture.md) · [Tabbed Dashboard Frontend](docs/tabbed_dashboard.md)

---

## Key Features

| Feature                         | Description                                                                                           |
| :------------------------------ | :---------------------------------------------------------------------------------------------------- |
| **Automated Ingestion**         | New requests flow in via Power Automate webhooks — zero manual data entry.                            |
| **Conversation Threading**      | Outlook `conversationId` groups email replies with the original request automatically.                |
| **Tabbed Multitasking**         | Open multiple request details as browser tabs within the dashboard. URL-hash state persistence.       |
| **Inline Communication**        | Reply to requesters via email directly from the request detail view.                                  |
| **Full Audit Trail**            | Every agent action (login, status change, assignment, email sent) is logged immutably.                |
| **Role-Based Access**           | Admin and User roles with staff management, password policies, and brute-force protection.            |
| **Multi-Channel Notifications** | SMTP relay and Microsoft Teams Adaptive Cards for outbound communication.                             |
| **Enterprise Design**           | Follows the Agilent Enterprise Design System — Inter typography, Phosphor icons, high-density layout. |

---

## Tech Stack

| Layer             | Technology                                 |
| :---------------- | :----------------------------------------- |
| **Runtime**       | Python 3.11                                |
| **Framework**     | Flask 3.x                                  |
| **Database**      | SQLite (file-based, zero-config)           |
| **WSGI Server**   | Gunicorn (multi-worker + threads)          |
| **Container**     | Docker (multi-stage build)                 |
| **Deployment**    | Azure App Service (Linux containers)       |
| **Frontend**      | Jinja2 templates, Tailwind CSS, vanilla JS |
| **Email Parsing** | Custom regex parser (`email_parser.py`)    |
| **Notifications** | SMTP relay, Teams webhooks, Power Automate |

---

## Getting Started

### Prerequisites

- **Python 3.11+** and `pip`
- (Optional) Docker for containerized runs

### Local Development

```bash
# 1. Clone the repository
git clone <repo-url> && cd AccountRequests-Dashboard

# 2. Create a virtual environment
python -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env   # Edit with your SMTP / webhook settings

# 5. Run the application
python run.py
```

The app initializes the SQLite database on first start (tables are created idempotently). Default staff users are seeded with the password `changeme123` — agents must change this on first login.

> 📖 _See also:_ [Local Development Guide](docs/local_development.md) · [Troubleshooting](docs/troubleshooting.md)

### Environment Variables

| Variable                 | Required | Default                  | Description                              |
| :----------------------- | :------: | :----------------------- | :--------------------------------------- |
| `FLASK_SECRET_KEY`       |    ✅    | dev fallback             | Session encryption key                   |
| `WEBHOOK_API_KEY`        |    —     | —                        | Optional API key for webhook auth        |
| `SMTP_SERVER`            |    —     | `smtp-relay.agilent.com` | SMTP relay hostname                      |
| `SMTP_PORT`              |    —     | `25`                     | SMTP relay port                          |
| `SMTP_FROM_EMAIL`        |    —     | `noreply@agilent.com`    | Sender address for outbound emails       |
| `DB_PATH`                |    —     | `./account_requests.db`  | Custom database file path (Azure mount)  |
| `GUNICORN_WORKERS`       |    —     | `3`                      | Number of Gunicorn workers               |
| `GUNICORN_THREADS`       |    —     | `2`                      | Threads per worker                       |
| `PORT` / `WEBSITES_PORT` |    —     | `8000`                   | Server bind port (Azure-injected)        |
| `TEAMS_WEBHOOK_LIST`     |    —     | —                        | Comma-separated Teams webhook URLs       |
| `EMAIL_TO_LIST`          |    —     | —                        | Comma-separated default email recipients |
| `SKIP_NOTIFICATIONS`     |    —     | `False`                  | Disable outbound notifications (dev)     |

> 📖 _See also:_ [Environment Configuration Reference](docs/environment.md)

---

## Project Structure

```
AccountRequests-Dashboard/
├── app.py                  # Flask application — routes, auth, template filters
├── database.py             # SQLite database layer — schema, migrations, CRUD
├── audit.py                # Append-only audit trail module
├── email_parser.py         # iLab email parser (key-value extraction)
├── notification_util.py    # SMTP + Teams + Power Automate notification engine
├── run.py                  # Gunicorn entry point (imports app, initializes DB)
├── gunicorn_config.py      # Gunicorn worker/thread/port configuration
├── startup.sh              # Docker CMD entrypoint script
├── Dockerfile              # Multi-stage Docker build (deps → app → debug-ssh)
├── requirements.txt        # Python dependencies
├── convert_env_to_azure.py # Utility: .env → Azure App Settings JSON
├── templates/
│   ├── base.html           # Base layout (nav, sidebar, Tailwind CDN)
│   ├── dashboard.html      # Main queue view + tab system
│   ├── login.html          # Staff login page
│   ├── users.html          # Admin: staff user management
│   ├── audit_log.html      # Cross-request audit log viewer
│   ├── import.html         # Manual request import form
│   ├── change_password.html
│   ├── error.html
│   ├── request_detail.html # Standalone detail (redirects to tab)
│   └── partials/
│       └── request_detail_content.html  # Shared detail partial (tab + standalone)
├── static/
│   └── (CSS, icons)
└── tests/
```

---

## Database Schema

Four tables in a single SQLite file (`account_requests.db`):

| Table              | Purpose                                                                           |
| :----------------- | :-------------------------------------------------------------------------------- |
| `requests`         | Core request records — requester info, status, assignment, conversation threading |
| `request_comments` | Activity stream — internal notes, inbound emails, outbound emails, status changes |
| `staff_users`      | Agent accounts — hashed passwords, roles (`admin`/`user`), active status          |
| `audit_log`        | Immutable, append-only record of every agent action                               |

The schema supports auto-migration: new columns are added via `ALTER TABLE` on startup with no manual SQL required.

> 📖 _See also:_ [Database Schema Reference](docs/database_schema.md) · [Data Model](docs/data_model.md)

---

## API Reference

All routes are prefixed with `/other` and require staff authentication unless noted.

### Webhook (Power Automate)

| Method | Endpoint                         |  Auth   | Description                                                        |
| :----: | :------------------------------- | :-----: | :----------------------------------------------------------------- |
| `POST` | `/other/api/webhook/new-request` | API Key | Ingest email from Power Automate. Supports conversation threading. |

### Request Management

| Method | Endpoint                              | Description                                        |
| :----: | :------------------------------------ | :------------------------------------------------- |
| `GET`  | `/other`                              | Dashboard — queue list with status filter + search |
| `GET`  | `/other/api/request/<key>/detail`     | Fetch request detail as HTML partial (for tabs)    |
| `POST` | `/other/api/request/<key>/status`     | Update status (Open / In Progress / Closed)        |
| `POST` | `/other/api/request/<key>/assign`     | Assign request to a staff member                   |
| `POST` | `/other/api/request/<key>/comment`    | Add an internal note                               |
| `POST` | `/other/api/request/<key>/send-email` | Send email to requester(s)                         |

### User Management

| Method | Endpoint                          | Access | Description                  |
| :----: | :-------------------------------- | :----: | :--------------------------- |
| `GET`  | `/other/users`                    | Admin  | Staff user management page   |
| `POST` | `/other/api/users`                | Admin  | Create a new staff user      |
| `POST` | `/other/api/users/<email>/toggle` | Admin  | Activate / deactivate a user |
| `POST` | `/other/api/users/<email>/role`   | Admin  | Change user role             |
| `POST` | `/other/api/change-password`      | Staff  | Change own password          |

> 📖 _See also:_ [API Reference (Full)](docs/api_reference.md)

---

## Authentication & Authorization

- **Session-based authentication** using Flask sessions with 8-hour lifetime.
- **Password hashing** via Werkzeug (`generate_password_hash` / `check_password_hash`).
- **Brute-force protection**: 5 failed attempts → 15-minute lockout (in-memory).
- **First-login flow**: New users must change the default password before accessing the dashboard.
- **Two roles**: `admin` (full access + user management) and `user` (standard agent).

> 📖 _See also:_ [Security Model](docs/security.md)

---

## Audit Trail

Every significant agent action writes an immutable row to the `audit_log` table. The audit system is designed to **never crash the application** — failures are logged but swallowed.

| Event                       | Trigger                                    |
| :-------------------------- | :----------------------------------------- |
| `agent.login.success`       | Successful staff login                     |
| `agent.login.failed`        | Failed login attempt                       |
| `agent.logout`              | Staff logout                               |
| `agent.password.change`     | Password updated                           |
| `agent.user.create`         | New staff user created                     |
| `agent.user.toggle`         | User activated/deactivated                 |
| `agent.user.role_change`    | User role changed                          |
| `request.status.update`     | Status changed (captures before/after)     |
| `request.assignment.update` | Request reassigned (captures before/after) |
| `request.comment.create`    | Internal note added                        |
| `request.email.send`        | Outbound email sent                        |
| `request.import.create`     | Request manually imported                  |
| `request.view`              | Request detail opened by agent             |

Access the cross-request audit viewer at **`/other/audit`** (staff only).

> 📖 _See also:_ [Audit Trail Implementation](docs/audit_trail.md)

---

## Notification System

The `notification_util.py` module provides multi-channel delivery using a shared `NotificationTemplate` pattern:

| Channel            | Transport                                | Config                                        |
| :----------------- | :--------------------------------------- | :-------------------------------------------- |
| **Email**          | SMTP relay (`smtp-relay.agilent.com:25`) | `SMTP_SERVER`, `SMTP_PORT`, `SMTP_FROM_EMAIL` |
| **Teams**          | Incoming Webhook → Adaptive Card         | `TEAMS_WEBHOOK_LIST`                          |
| **Power Automate** | HTTP POST → email flow                   | `POWER_AUTOMATE_WEBHOOK_URL`                  |

Notifications include environment-aware SSL handling (bypasses corporate proxy SSL in local dev) and threaded parallel delivery via `ThreadPoolExecutor`.

> 📖 _See also:_ [Notification System](docs/notifications.md)

---

## Deployment

### Docker

The `Dockerfile` uses a **multi-stage build** for minimal image size:

```bash
# Production build
docker build -t account-requests-dashboard .
docker run -p 8000:8000 --env-file .env account-requests-dashboard

# Debug build (includes SSH for Azure troubleshooting)
docker build --target debug-ssh -t account-requests-dashboard:debug .
```

### Azure App Service

The application runs as a Linux container on Azure App Service. Key configuration:

- **Bind port**: Reads `PORT` / `WEBSITES_PORT` env vars injected by Azure.
- **Health check**: `GET /healthz` (30s interval, 5 retries).
- **Persistent storage**: Mount Azure File Share and set `DB_PATH` to preserve SQLite across restarts.
- **Environment config**: Use `convert_env_to_azure.py` to transform `.env` into Azure App Settings JSON.

> 📖 _See also:_ [Deployment Guide](docs/deployment.md) · [Azure Configuration](docs/azure_config.md)

---

## UI / Design System

The dashboard follows the **Agilent Enterprise Design System**:

- **Typography**: Inter (sans-serif), SF Mono (monospace for reference codes)
- **Iconography**: Phosphor Icons (light weight)
- **Layout**: High-density data tables, sticky tab bar, fixed sidebar detail panels
- **CSS Strategy**: Tailwind-first for detail views, coexisting with legacy global styles
- **Tab System**: `TabManager` JS object with URL-hash state persistence and async partial loading
- **Animations**: Subtle `fadeIn` + `translateY` transitions for premium feel

> 📖 _See also:_ [UI/UX Design System](docs/design_system.md) · [Tabbed Dashboard Architecture](docs/tabbed_dashboard.md) · [Component Library](docs/components.md)

---

## Contributing

This is an internal Agilent tool. Please follow team conventions:

1. Branch from `main` for new features.
2. Test locally with `python run.py` before pushing.
3. All audit-relevant changes must include corresponding `audit.log_audit_event()` calls.
4. Update this README and relevant `docs/` pages when adding features.

> 📖 _See also:_ [Development Workflow](docs/development_workflow.md) · [Testing Guide](docs/testing.md)

---

## Future Documentation Roadmap

The following subdocuments are planned for the `docs/` directory:

| Document                                                       | Status | Topic                                                   |
| :------------------------------------------------------------- | :----: | :------------------------------------------------------ |
| [`docs/architecture.md`](docs/architecture.md)                 |   🔲   | System architecture, module responsibilities, data flow |
| [`docs/api_reference.md`](docs/api_reference.md)               |   🔲   | Full API specification with request/response examples   |
| [`docs/database_schema.md`](docs/database_schema.md)           |   🔲   | Table definitions, indexes, migration strategy          |
| [`docs/data_model.md`](docs/data_model.md)                     |   🔲   | Entity relationships, request lifecycle states          |
| [`docs/email_parser.md`](docs/email_parser.md)                 |   🔲   | iLab email format, parsing logic, edge cases            |
| [`docs/power_automate.md`](docs/power_automate.md)             |   🔲   | O365 flow configuration, webhook payload spec           |
| [`docs/tabbed_dashboard.md`](docs/tabbed_dashboard.md)         |   🔲   | Frontend tab system, TabManager JS, CSS layout          |
| [`docs/design_system.md`](docs/design_system.md)               |   🔲   | Enterprise UI tokens, typography, components            |
| [`docs/components.md`](docs/components.md)                     |   🔲   | Reusable UI components and patterns                     |
| [`docs/audit_trail.md`](docs/audit_trail.md)                   |   🔲   | Audit event taxonomy, query patterns, viewer            |
| [`docs/notifications.md`](docs/notifications.md)               |   🔲   | Multi-channel delivery, Adaptive Cards, templates       |
| [`docs/security.md`](docs/security.md)                         |   🔲   | Auth model, rate limiting, session management           |
| [`docs/deployment.md`](docs/deployment.md)                     |   🔲   | Docker build, Azure App Service, health checks          |
| [`docs/azure_config.md`](docs/azure_config.md)                 |   🔲   | Azure-specific settings, persistent storage, SSL        |
| [`docs/environment.md`](docs/environment.md)                   |   🔲   | Complete env var reference with examples                |
| [`docs/local_development.md`](docs/local_development.md)       |   🔲   | Setup, common pitfalls, debugging tips                  |
| [`docs/troubleshooting.md`](docs/troubleshooting.md)           |   🔲   | Known issues, FAQ, debugging recipes                    |
| [`docs/development_workflow.md`](docs/development_workflow.md) |   🔲   | Git conventions, PR process, code standards             |
| [`docs/testing.md`](docs/testing.md)                           |   🔲   | Test strategy, fixtures, CI integration                 |

---

<sub>Maintained by the Agilent iLab Support Engineering Team · Last updated February 2026</sub>
