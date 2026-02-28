"""
Database Module for Account Requests Dashboard
Handles local SQLite database for storing account requests and comments.
"""
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash

DB_NAME = 'account_requests.db'

def get_db_path():
    """Get absolute path to the database file.
    Uses DB_PATH env var if set (for Azure persistent mount), otherwise
    defaults to the project directory.
    """
    custom_path = os.environ.get('DB_PATH')
    if custom_path:
        return custom_path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), DB_NAME)

def get_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row  # Return rows as dict-like objects
    return conn

@contextmanager
def get_db():
    """Context manager that yields a connection and always closes it."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize database tables."""
    with get_db() as conn:
        c = conn.cursor()

        # Create requests table
        c.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_key TEXT UNIQUE NOT NULL,
                status TEXT DEFAULT 'Open',
                requester_email TEXT NOT NULL,
                requester_name TEXT,
                organization TEXT,
                lab_name TEXT,
                request_type TEXT DEFAULT 'Account Request',
                original_subject TEXT,
                original_body TEXT,
                source_email_id TEXT,
                conversation_id TEXT,
                assigned_to TEXT,
                ilab_link TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP
            )
        ''')

        # Create request_comments table for internal notes and email trail
        c.execute('''
            CREATE TABLE IF NOT EXISTS request_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                author_email TEXT NOT NULL,
                author_name TEXT,
                comment_type TEXT DEFAULT 'note',
                body TEXT NOT NULL,
                email_subject TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES requests(id)
            )
        ''')

        # Create index on request_key for fast lookup
        c.execute('CREATE INDEX IF NOT EXISTS idx_request_key ON requests(request_key)')

        # ── Audit Log Table ──────────────────────────────────────────────────────
        # Append-only record of every significant support-agent action.
        # This table must NEVER be updated or deleted from application code.
        c.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id    TEXT    UNIQUE NOT NULL,
                timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                actor_email TEXT    NOT NULL,
                actor_ip    TEXT,
                action      TEXT    NOT NULL,
                target_type TEXT,
                target_id   TEXT,
                details     TEXT,
                success     INTEGER NOT NULL DEFAULT 1
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_audit_actor_email ON audit_log(actor_email)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_audit_action      ON audit_log(action)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_audit_target_id   ON audit_log(target_id)')
        # ────────────────────────────────────────────────────────────────────────

        # ── Staff Users Table ─────────────────────────────────────────────────
        c.execute('''
            CREATE TABLE IF NOT EXISTS staff_users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                email         TEXT    UNIQUE NOT NULL,
                name          TEXT    NOT NULL,
                password_hash TEXT    NOT NULL,
                is_active     INTEGER DEFAULT 1,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP,
                must_change_password INTEGER DEFAULT 1,
                role          TEXT    DEFAULT 'user'
            )
        ''')
        # ────────────────────────────────────────────────────────────────────────

        conn.commit()

    # Run migrations for existing databases
    migrate_db()

    # Seed staff users if table is empty
    seed_staff_users()

    print(f"✅ Database initialized: {get_db_path()}")


def migrate_db():
    """Apply schema migrations for existing databases."""
    with get_db() as conn:
        c = conn.cursor()

        # Migration: Add ilab_link column if it doesn't exist
        try:
            c.execute('ALTER TABLE requests ADD COLUMN ilab_link TEXT')
            conn.commit()
            print("  ↳ Migration applied: added 'ilab_link' column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add lab_name column if it doesn't exist
        try:
            c.execute('ALTER TABLE requests ADD COLUMN lab_name TEXT')
            conn.commit()
            print("  ↳ Migration applied: added 'lab_name' column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add must_change_password column to staff_users
        try:
            c.execute('ALTER TABLE staff_users ADD COLUMN must_change_password INTEGER DEFAULT 1')
            conn.commit()
            print("  ↳ Migration applied: added 'must_change_password' column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add role column to staff_users
        try:
            c.execute("ALTER TABLE staff_users ADD COLUMN role TEXT DEFAULT 'user'")
            conn.commit()
            print("  ↳ Migration applied: added 'role' column")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Create audit_log table for existing databases that pre-date it
        c.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id    TEXT    UNIQUE NOT NULL,
                timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
                actor_email TEXT    NOT NULL,
                actor_ip    TEXT,
                action      TEXT    NOT NULL,
                target_type TEXT,
                target_id   TEXT,
                details     TEXT,
                success     INTEGER NOT NULL DEFAULT 1
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_audit_actor_email ON audit_log(actor_email)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_audit_action      ON audit_log(action)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_audit_target_id   ON audit_log(target_id)')
        conn.commit()


def generate_request_key():
    """Generate the next request key (ACCT-0001 format)."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT MAX(id) FROM requests')
        result = c.fetchone()[0]

    next_num = (result or 0) + 1
    return f"ACCT-{next_num:04d}"


def create_request(requester_email, requester_name=None, organization=None,
                   original_subject=None, original_body=None, source_email_id=None,
                   conversation_id=None, request_type='Account Request', ilab_link=None,
                   lab_name=None):
    """
    Create a new account request.
    Returns the request dict with generated key.
    """
    request_key = generate_request_key()
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        c = conn.cursor()

        c.execute('''
            INSERT INTO requests (
                request_key, requester_email, requester_name, organization,
                lab_name, request_type, original_subject, original_body,
                source_email_id, conversation_id, ilab_link, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (request_key, requester_email.lower().strip(), requester_name, organization,
              lab_name, request_type, original_subject, original_body, source_email_id,
              conversation_id, ilab_link, now, now))

        request_id = c.lastrowid
        conn.commit()

    return {
        'id': request_id,
        'request_key': request_key,
        'status': 'Open',
        'requester_email': requester_email,
        'requester_name': requester_name,
        'organization': organization,
        'lab_name': lab_name,
        'request_type': request_type,
        'original_subject': original_subject,
        'original_body': original_body,
        'conversation_id': conversation_id,
        'ilab_link': ilab_link,
        'created_at': now
    }


def get_request_by_conversation_id(conversation_id):
    """Get a request by its Outlook conversation ID."""
    if not conversation_id:
        return None
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM requests WHERE conversation_id = ? ORDER BY created_at ASC LIMIT 1', (conversation_id,))
        row = c.fetchone()
    return dict(row) if row else None


def get_request_by_key(request_key):
    """Get a request by its key (e.g., ACCT-0001)."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM requests WHERE request_key = ?', (request_key.upper().strip(),))
        row = c.fetchone()
    return dict(row) if row else None


def get_all_requests(status_filter=None, search_query=None):
    """
    Get all requests, optionally filtered by status and/or search query.
    Returns newest first.
    """
    query = 'SELECT * FROM requests WHERE 1=1'
    params = []

    if status_filter and status_filter != 'All':
        query += ' AND status = ?'
        params.append(status_filter)

    if search_query:
        query += ' AND (requester_email LIKE ? OR requester_name LIKE ? OR request_key LIKE ?)'
        search_pattern = f'%{search_query}%'
        params.extend([search_pattern, search_pattern, search_pattern])

    query += ' ORDER BY created_at DESC'

    with get_db() as conn:
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
    return [dict(row) for row in rows]


def update_request_status(request_key, new_status, updated_by=None):
    """
    Update the status of a request.
    Valid statuses: 'Open', 'In Progress', 'Closed'
    """
    valid_statuses = ['Open', 'In Progress', 'Closed']
    if new_status not in valid_statuses:
        return False

    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        c = conn.cursor()

        if new_status == 'Closed':
            c.execute('''
                UPDATE requests
                SET status = ?, updated_at = ?, closed_at = ?
                WHERE request_key = ?
            ''', (new_status, now, now, request_key))
        else:
            c.execute('''
                UPDATE requests
                SET status = ?, updated_at = ?, closed_at = NULL
                WHERE request_key = ?
            ''', (new_status, now, request_key))

        updated = c.rowcount > 0
        conn.commit()

    return updated


def assign_request(request_key, assignee_email):
    """Assign a request to a staff member."""
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        c = conn.cursor()

        c.execute('''
            UPDATE requests
            SET assigned_to = ?, updated_at = ?
            WHERE request_key = ?
        ''', (assignee_email.lower().strip() if assignee_email else None, now, request_key))

        updated = c.rowcount > 0
        conn.commit()

    return updated


def add_comment(request_key, author_email, body, author_name=None,
                comment_type='note', email_subject=None):
    """
    Add a comment/note to a request.
    comment_type: 'note', 'email_sent', 'email_received'
    """
    # First get the request ID
    request = get_request_by_key(request_key)
    if not request:
        return None

    now = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        c = conn.cursor()

        c.execute('''
            INSERT INTO request_comments (
                request_id, author_email, author_name, comment_type,
                body, email_subject, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (request['id'], author_email.lower().strip(), author_name,
              comment_type, body, email_subject, now))

        comment_id = c.lastrowid

        # Also update request's updated_at
        c.execute('UPDATE requests SET updated_at = ? WHERE id = ?', (now, request['id']))

        conn.commit()

    return {
        'id': comment_id,
        'request_id': request['id'],
        'author_email': author_email,
        'author_name': author_name,
        'comment_type': comment_type,
        'body': body,
        'email_subject': email_subject,
        'created_at': now
    }


def get_comments_for_request(request_key):
    """Get all comments for a request, ordered by created_at."""
    request = get_request_by_key(request_key)
    if not request:
        return []

    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT * FROM request_comments
            WHERE request_id = ?
            ORDER BY created_at ASC
        ''', (request['id'],))
        rows = c.fetchall()
    return [dict(row) for row in rows]


def get_request_counts():
    """Get counts by status for dashboard display."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT status, COUNT(*) as count
            FROM requests
            GROUP BY status
        ''')
        rows = c.fetchall()

    counts = {'Open': 0, 'In Progress': 0, 'Closed': 0, 'Total': 0}
    for row in rows:
        counts[row['status']] = row['count']
        counts['Total'] += row['count']

    return counts


# ─────────────────────────────────────────────────────────────────────────────
# Staff Management (DB-backed)
# ─────────────────────────────────────────────────────────────────────────────

# Legacy seed data — used ONLY to populate staff_users table on first run.
_SEED_STAFF = [
    {'email': 'nadia.clark@agilent.com', 'name': 'Nadia Clark'},
    {'email': 'william.lai@agilent.com', 'name': 'William Lai'},
    {'email': 'elvira.carrera@agilent.com', 'name': 'Elvira Carrera'},
    {'email': 'vinod.rajendran@agilent.com', 'name': 'Vinod Rajendran'},
    {'email': 'guilherme.vieira-machado@agilent.com', 'name': 'Guilherme Vieira-Machado'},
]

_DEFAULT_PASSWORD = 'changeme123'


def seed_staff_users():
    """Seed the staff_users table from the legacy list if it's empty."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM staff_users')
        count = c.fetchone()[0]

        if count == 0:
            hashed = generate_password_hash(_DEFAULT_PASSWORD)
            for user in _SEED_STAFF:
                c.execute('''
                    INSERT OR IGNORE INTO staff_users (email, name, password_hash, role)
                    VALUES (?, ?, ?, 'admin')
                ''', (user['email'].lower().strip(), user['name'], hashed))
            conn.commit()
            print(f"  ⚠️  Seeded {len(_SEED_STAFF)} staff users with default password — change on first login")


def get_staff_users():
    """Return list of active staff users as [{email, name}, ...]."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT email, name FROM staff_users WHERE is_active = 1 ORDER BY name')
        rows = c.fetchall()
    return [{'email': r['email'], 'name': r['name']} for r in rows]


def is_staff_user(email):
    """Check if an email belongs to an active staff member."""
    if not email:
        return False
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT 1 FROM staff_users WHERE email = ? AND is_active = 1',
                  (email.lower().strip(),))
        row = c.fetchone()
    return row is not None


def get_staff_name(email):
    """Get staff member's name by email."""
    if not email:
        return None
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT name FROM staff_users WHERE email = ?',
                  (email.lower().strip(),))
        row = c.fetchone()
    return row['name'] if row else None


def verify_staff_credentials(email, password):
    """Verify email + password. Returns user dict or None."""
    if not email or not password:
        return None
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM staff_users WHERE email = ? AND is_active = 1',
                  (email.lower().strip(),))
        row = c.fetchone()
    if row and check_password_hash(row['password_hash'], password):
        return dict(row)
    return None


def set_staff_password(email, new_password):
    """Set/update a staff user's password. Also clears must_change_password flag."""
    hashed = generate_password_hash(new_password)
    with get_db() as conn:
        c = conn.cursor()
        c.execute('UPDATE staff_users SET password_hash = ?, must_change_password = 0 WHERE email = ?',
                  (hashed, email.lower().strip()))
        updated = c.rowcount > 0
        conn.commit()
    return updated


def update_last_login(email):
    """Update last_login_at timestamp for a user."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        c = conn.cursor()
        c.execute('UPDATE staff_users SET last_login_at = ? WHERE email = ?',
                  (now, email.lower().strip()))
        conn.commit()


def get_all_staff_users():
    """Return all staff users with full details (for admin page)."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT id, email, name, role, is_active, created_at, last_login_at FROM staff_users ORDER BY name')
        rows = c.fetchall()
    return [dict(r) for r in rows]


def get_staff_role(email):
    """Get role for a staff user. Returns 'admin' or 'user' (or None)."""
    if not email:
        return None
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT role FROM staff_users WHERE email = ? AND is_active = 1',
                  (email.lower().strip(),))
        row = c.fetchone()
    return row['role'] if row else None


def set_staff_role(email, new_role):
    """Set a staff user's role. Returns True if updated."""
    if new_role not in ('admin', 'user'):
        return False
    with get_db() as conn:
        c = conn.cursor()
        c.execute('UPDATE staff_users SET role = ? WHERE email = ?',
                  (new_role, email.lower().strip()))
        updated = c.rowcount > 0
        conn.commit()
    return updated


def create_staff_user(email, name, password=None):
    """Create a new staff user. Returns the user dict or None if email already exists."""
    password = password or _DEFAULT_PASSWORD
    hashed = generate_password_hash(password)
    with get_db() as conn:
        c = conn.cursor()
        try:
            c.execute('''
                INSERT INTO staff_users (email, name, password_hash, must_change_password)
                VALUES (?, ?, ?, 1)
            ''', (email.lower().strip(), name.strip(), hashed))
            conn.commit()
            user_id = c.lastrowid
        except sqlite3.IntegrityError:
            return None
    return {'id': user_id, 'email': email.lower().strip(), 'name': name.strip()}


def toggle_staff_active(email):
    """Toggle a staff user's active status. Returns new is_active value or None."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT is_active FROM staff_users WHERE email = ?', (email.lower().strip(),))
        row = c.fetchone()
        if not row:
            return None
        new_status = 0 if row['is_active'] else 1
        c.execute('UPDATE staff_users SET is_active = ? WHERE email = ?',
                  (new_status, email.lower().strip()))
        conn.commit()
    return new_status


def must_change_password(email):
    """Check if user must change password on login."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute('SELECT must_change_password FROM staff_users WHERE email = ?',
                  (email.lower().strip(),))
        row = c.fetchone()
    return bool(row and row['must_change_password'])
