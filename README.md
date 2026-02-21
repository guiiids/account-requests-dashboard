# AccountRequests-Dashboard

![Status](https://img.shields.io/badge/status-active-success.svg)
![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)

> A staff-only dashboard for managing iLab account signup requests with automated email parsing and workflow management.

## 📖 Overview

The **AccountRequests-Dashboard** streamlines the process of handling new user account requests for iLab. It replaces manual email tracking with a centralized dashboard that automatically ingests request emails, parses key details (requester, organization), and allows staff to manage the approval lifecycle.

**Key Features:**
-   **Automated Ingestion**: Webhook integration with Power Automate to parse incoming emails.
-   **Smart Parsing**: Extracts requester name, email, and institution from unstructured email bodies.
-   **Worklow Management**: distinct states (Open, In Progress, Closed) and assignment logic.
-   **Conversation Threading**: Groups follow-up emails into a single request thread.
-   **Staff-Only Access**: Secure login restricted to authorized support staff.

## 📸 Screenshots
*(Placeholder for dashboard screenshot)*

## 🛠 Prerequisites

Ensure you have the following installed:
-   Python 3.11+
-   SQLite (Pre-installed on macOS/Linux)

## 🚀 Installation

### 1. Clone the repository
```bash
git clone <repository_url>
cd AccountRequests-Dashboard
```

### 2. Set up virtual environment
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Environment Configuration
Create a `.env` file based on the example:
```bash
cp .env.example .env
```
**Required Variables:**
-   `FLASK_SECRET_KEY`: Random string for session security.
-   `WEBHOOK_API_KEY`: Secret key for validating Power Automate requests.
-   `SMTP_SERVER`: (Optional) SMTP server for outgoing notifications.

## 🏃‍♂️ Usage

### Start the Application
```bash
python app.py
```
The dashboard will be available at `http://localhost:5006`.

### Initial Setup
On first run, the application automatically initializes the SQLite database at `account_requests.db`.

## 📂 Project Structure

```text
.
├── app.py                  # Main Flask application & routes
├── database.py             # SQLite schema and data access layer
├── email_parser.py         # Regex logic for parsing email content
├── notification_util.py    # Utilities for sending emails/Teams messages
├── templates/              # Jinja2 HTML templates
│   ├── dashboard.html      # Main view
│   └── partials/           # HTMX partials for dynamic tabs
├── static/                 # CSS/JS assets
└── account_requests.db     # Local SQLite database (auto-generated)
```

## 🔌 API & Webhooks

### Investion Webhook
**Endpoint**: `POST /api/webhook/new-request`
**Headers**: `X-API-Key: <WEBHOOK_API_KEY>`
**Payload**:
```json
{
  "subject": "New Account Request",
  "body": "Requester: John Doe...",
  "from": "john.doe@example.com",
  "messageId": "<unique-id>",
  "conversationId": "<thread-id>"
}
```

## 🧪 Testing

To run the test suite:
```bash
pytest tests/
```

## 🤝 Contributing
1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/NewParser`)
3.  Commit your Changes (`git commit -m 'Improve email parsing logic'`)
4.  Push to the Branch (`git push origin feature/NewParser`)
5.  Open a Pull Request
# account-requests-dashboard
