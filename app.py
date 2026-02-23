"""
Account Requests Dashboard - Flask Application
A staff-only dashboard for managing iLab account signup requests.
"""
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import database
import audit
import email_parser
import notification_util
import os
from datetime import datetime, timedelta
from functools import wraps
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'account-requests-dev-secret-2026')
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)


# =============================================================================
# Brute-Force Rate Limiting (in-memory)
# =============================================================================

_LOGIN_ATTEMPTS = {}  # {email: [datetime, ...]}
_MAX_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def _is_login_locked(email):
    """Check if email is temporarily locked due to failed attempts."""
    attempts = _LOGIN_ATTEMPTS.get(email, [])
    cutoff = datetime.now() - timedelta(minutes=_LOCKOUT_MINUTES)
    recent = [t for t in attempts if t > cutoff]
    _LOGIN_ATTEMPTS[email] = recent
    return len(recent) >= _MAX_ATTEMPTS


def _record_failed_attempt(email):
    """Record a failed login attempt."""
    _LOGIN_ATTEMPTS.setdefault(email, []).append(datetime.now())


def _clear_login_attempts(email):
    """Clear attempts after successful login."""
    _LOGIN_ATTEMPTS.pop(email, None)


# =============================================================================
# Authentication / Authorization
# =============================================================================

def staff_required(f):
    """Decorator to require staff login for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_email = session.get('user_email')
        if not user_email or not database.is_staff_user(user_email):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin role for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_email = session.get('user_email')
        if not user_email or not database.is_staff_user(user_email):
            return redirect(url_for('login'))
        if database.get_staff_role(user_email) != 'admin':
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get the current logged-in user info."""
    email = session.get('user_email')
    if email:
        return {
            'email': email,
            'name': database.get_staff_name(email) or email.split('@')[0],
            'role': database.get_staff_role(email) or 'user',
        }
    return None


@app.context_processor
def inject_user():
    """Inject current user into all templates."""
    return {'current_user': get_current_user()}


@app.template_filter('format_datetime')
def format_datetime(value, fmt='friendly'):
    """Format a date string or datetime object into a human-friendly local time."""
    if not value:
        return ''
    date_obj = None
    if isinstance(value, str):
        # Normalize: replace T separator with space, strip trailing Z
        normalized = value.replace('T', ' ').rstrip('Z').strip()
        formats_to_try = [
            '%Y-%m-%d %H:%M:%S.%f',  # 2026-02-19 21:47:42.434726
            '%Y-%m-%d %H:%M:%S',     # 2026-02-19 21:47:42
            '%Y-%m-%d %H:%M',        # 2026-02-19 21:47
            '%Y-%m-%d',              # 2026-02-04
        ]
        for f in formats_to_try:
            try:
                date_obj = datetime.strptime(normalized, f)
                break
            except ValueError:
                continue
        if date_obj is None:
            return value  # Fallback: return original string unchanged
    else:
        date_obj = value

    # Human-friendly format: "Feb 19, 2026 at 9:47 PM"
    # For date-only values (midnight), omit the time portion
    if date_obj.hour == 0 and date_obj.minute == 0 and date_obj.second == 0:
        return date_obj.strftime('%b %-d, %Y')
    return date_obj.strftime('%b %-d, %Y at %-I:%M %p')


@app.template_filter('get_initials')
def get_initials(name):
    """Get initials from a name."""
    if not name:
        return '?'
    parts = name.split()
    if len(parts) == 1:
        return parts[0][:1].upper()
    return (parts[0][:1] + parts[-1][:1]).upper()


@app.template_filter('format_email_body')
def format_email_body(value):
    """Strip HTML and normalize whitespace for clean display of email bodies."""
    if not value:
        return ''
    return email_parser.strip_html(value)


@app.template_filter('status_color_class')
def status_color_class(status):
    """Return Tailwind classes for status badge."""
    status = (status or '').lower()
    if status == 'open':
        return 'bg-blue-50 text-blue-700 border-blue-200'
    elif status == 'in progress':
        return 'bg-amber-50 text-amber-700 border-amber-200'
    elif status == 'closed':
        return 'bg-green-50 text-green-700 border-green-200'
    return 'bg-gray-50 text-gray-700 border-gray-200'


# =============================================================================
# Routes - Public
# =============================================================================

@app.route('/')
def index():
    """Root redirect - send visitors straight to the dashboard."""
    return redirect(url_for('dashboard'))


@app.route('/other/login', methods=['GET', 'POST'])
def login():
    """Staff login page with email + password."""
    error = None

    if request.method == 'POST':
        email = request.form.get('email', '').lower().strip()
        password = request.form.get('password', '')

        # Rate limiting check
        if _is_login_locked(email):
            error = 'Too many failed attempts. Please try again in 15 minutes.'
            return render_template('login.html', error=error)

        user = database.verify_staff_credentials(email, password)
        if user:
            session['user_email'] = email
            session.permanent = bool(request.form.get('remember'))
            _clear_login_attempts(email)
            database.update_last_login(email)
            # ── AUDIT: successful login ──────────────────────────────────────
            audit.log_audit_event(
                actor_email=email,
                action='agent.login.success',
                target_type='system',
            )
            return redirect(url_for('force_change_password') if database.must_change_password(email) else url_for('dashboard'))
        else:
            _record_failed_attempt(email)
            # ── AUDIT: failed login attempt ──────────────────────────────────
            audit.log_audit_event(
                actor_email=email or 'unknown',
                action='agent.login.failed',
                target_type='system',
                details={'attempted_email': email},
                success=False,
            )
            error = 'Invalid email or password.'

    return render_template('login.html', error=error, attempted_email=request.form.get('email', '') if request.method == 'POST' else '')


@app.route('/other/logout')
def logout():
    """Log out the current user."""
    user = get_current_user()
    if user:
        # ── AUDIT: logout ────────────────────────────────────────────────────
        audit.log_audit_event(
            actor_email=user['email'],
            action='agent.logout',
            target_type='system',
        )
    session.pop('user_email', None)
    return redirect(url_for('login'))


# =============================================================================
# Routes - Force Password Change
# =============================================================================

@app.route('/other/change-password', methods=['GET', 'POST'])
@staff_required
def force_change_password():
    """Force user to change password on first login."""
    user = get_current_user()
    error = None
    success = None

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(new_password) < 8:
            error = 'Password must be at least 8 characters.'
        elif new_password != confirm_password:
            error = 'Passwords do not match.'
        else:
            database.set_staff_password(user['email'], new_password)
            audit.log_audit_event(
                actor_email=user['email'],
                action='agent.password.change',
                target_type='system',
                details={'forced': True},
            )
            return redirect(url_for('dashboard'))

    return render_template('change_password.html', error=error)


# =============================================================================
# Routes - User Management (Staff Only)
# =============================================================================

@app.route('/other/users')
@admin_required
def manage_users():
    """Admin page to manage staff users."""
    users = database.get_all_staff_users()
    return render_template('users.html', users=users, default_password=database._DEFAULT_PASSWORD)


@app.route('/other/api/users', methods=['POST'])
@admin_required
def api_create_user():
    """Create a new staff user."""
    data = request.get_json() or {}
    email = data.get('email', '').lower().strip()
    name = data.get('name', '').strip()

    if not email or not name:
        return jsonify({'success': False, 'error': 'Email and name are required'}), 400

    user = database.create_staff_user(email, name)
    if not user:
        return jsonify({'success': False, 'error': 'A user with this email already exists'}), 400

    actor = get_current_user()
    audit.log_audit_event(
        actor_email=actor['email'],
        action='agent.user.create',
        target_type='user',
        target_id=email,
        details={'name': name},
    )

    return jsonify({'success': True, 'user': user})


@app.route('/other/api/users/<email>/toggle', methods=['POST'])
@admin_required
def api_toggle_user(email):
    """Activate or deactivate a staff user."""
    actor = get_current_user()
    if actor['email'].lower() == email.lower():
        return jsonify({'success': False, 'error': 'You cannot deactivate yourself'}), 400

    new_status = database.toggle_staff_active(email)
    if new_status is None:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    audit.log_audit_event(
        actor_email=actor['email'],
        action='agent.user.toggle',
        target_type='user',
        target_id=email,
        details={'is_active': new_status},
    )

    return jsonify({'success': True, 'is_active': new_status})


@app.route('/other/api/users/<email>/role', methods=['POST'])
@admin_required
def api_change_role(email):
    """Change a staff user's role (admin/user)."""
    actor = get_current_user()
    if actor['email'].lower() == email.lower():
        return jsonify({'success': False, 'error': 'You cannot change your own role'}), 400

    data = request.get_json() or {}
    new_role = data.get('role', '')
    if new_role not in ('admin', 'user'):
        return jsonify({'success': False, 'error': 'Invalid role'}), 400

    success = database.set_staff_role(email, new_role)
    if not success:
        return jsonify({'success': False, 'error': 'User not found'}), 404

    audit.log_audit_event(
        actor_email=actor['email'],
        action='agent.user.role_change',
        target_type='user',
        target_id=email,
        details={'new_role': new_role},
    )

    return jsonify({'success': True, 'role': new_role})


# =============================================================================
# Routes - Dashboard (Staff Only)
# =============================================================================

@app.route('/other')
@staff_required
def dashboard():
    """Main dashboard showing all account requests."""
    status_filter = request.args.get('status', 'All')
    search_query = request.args.get('search', '')

    requests_list = database.get_all_requests(
        status_filter=status_filter if status_filter != 'All' else None,
        search_query=search_query if search_query else None
    )

    counts = database.get_request_counts()

    return render_template(
        'dashboard.html',
        requests=requests_list,
        counts=counts,
        current_filter=status_filter,
        search_query=search_query,
        staff_users=database.get_staff_users()
    )


@app.route('/other/request/<request_key>')
@staff_required
def request_detail(request_key):
    """
    Redirect to dashboard with tab hash for the requested item.
    This preserves backward compatibility with direct URLs.
    """
    return redirect(url_for('dashboard') + f'#tab={request_key}')


@app.route('/other/api/request/<request_key>/detail')
@staff_required
def api_request_detail(request_key):
    """
    API endpoint for loading request details into tabs.
    Returns rendered HTML partial for tab content.
    """
    req = database.get_request_by_key(request_key)

    if not req:
        return jsonify({'error': 'Request not found'}), 404

    comments = database.get_comments_for_request(request_key)
    audit_entries = audit.get_audit_log_for_request(request_key)

    user = get_current_user()
    # ── AUDIT: request viewed ────────────────────────────────────────────────
    audit.log_audit_event(
        actor_email=user['email'],
        action='request.view',
        target_type='request',
        target_id=request_key,
    )

    # Return rendered partial HTML for tab content
    return render_template(
        'partials/request_detail_content.html',
        request=req,
        comments=comments,
        audit_entries=audit_entries,
        staff_users=database.get_staff_users()
    )


# =============================================================================
# API Routes - Password Management
# =============================================================================

@app.route('/other/api/change-password', methods=['POST'])
@staff_required
def api_change_password():
    """Change the current user's password."""
    data = request.get_json() or {}
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401

    # Verify current password
    if not database.verify_staff_credentials(user['email'], current_password):
        return jsonify({'success': False, 'error': 'Current password is incorrect'}), 400

    # Enforce minimum length
    if len(new_password) < 8:
        return jsonify({'success': False, 'error': 'New password must be at least 8 characters'}), 400

    # Set new password
    success = database.set_staff_password(user['email'], new_password)

    if success:
        audit.log_audit_event(
            actor_email=user['email'],
            action='agent.password.change',
            target_type='system',
        )

    return jsonify({'success': success})


# =============================================================================
# API Routes - Request Management
# =============================================================================

@app.route('/other/api/request/<request_key>/status', methods=['POST'])
@staff_required
def api_update_status(request_key):
    """Update request status."""
    data = request.get_json() or {}
    new_status = data.get('status')

    if not new_status:
        return jsonify({'success': False, 'error': 'Status is required'}), 400

    # Capture the current status BEFORE the update for a complete audit record.
    existing = database.get_request_by_key(request_key)
    old_status = existing.get('status') if existing else None

    success = database.update_request_status(request_key, new_status)

    user = get_current_user()
    if success:
        # ── AUDIT: status changed ────────────────────────────────────────────
        audit.log_audit_event(
            actor_email=user['email'],
            action='request.status.update',
            target_type='request',
            target_id=request_key,
            details={'from': old_status, 'to': new_status},
        )
        # Keep the human-readable activity comment for the activity stream.
        database.add_comment(
            request_key,
            author_email=user['email'],
            author_name=user['name'],
            body=f"Changed status to: {new_status}",
            comment_type='activity_log'
        )

    return jsonify({'success': success})


@app.route('/other/api/request/<request_key>/assign', methods=['POST'])
@staff_required
def api_assign_request(request_key):
    """Assign request to a staff member."""
    data = request.get_json() or {}
    assignee_email = data.get('assignee_email')

    # Capture the current assignee BEFORE the update.
    existing = database.get_request_by_key(request_key)
    old_assignee = existing.get('assigned_to') if existing else None

    success = database.assign_request(request_key, assignee_email)

    user = get_current_user()
    if success:
        assignee_name = database.get_staff_name(assignee_email) or assignee_email
        # ── AUDIT: assignment changed ────────────────────────────────────────
        audit.log_audit_event(
            actor_email=user['email'],
            action='request.assignment.update',
            target_type='request',
            target_id=request_key,
            details={
                'from': old_assignee,
                'to': assignee_email,
                'assignee_name': assignee_name,
            },
        )
        database.add_comment(
            request_key,
            author_email=user['email'],
            author_name=user['name'],
            body=f"Assigned to: {assignee_name}",
            comment_type='activity_log'
        )

    return jsonify({'success': success})


@app.route('/other/api/request/<request_key>/comment', methods=['POST'])
@staff_required
def api_add_comment(request_key):
    """Add an internal note to a request."""
    data = request.get_json() or {}
    body = data.get('body', '').strip()

    if not body:
        return jsonify({'success': False, 'error': 'Comment body is required'}), 400

    user = get_current_user()
    comment = database.add_comment(
        request_key,
        author_email=user['email'],
        author_name=user['name'],
        body=body,
        comment_type='note'
    )

    if comment:
        # ── AUDIT: internal note added ───────────────────────────────────────
        audit.log_audit_event(
            actor_email=user['email'],
            action='request.comment.create',
            target_type='request',
            target_id=request_key,
            details={
                'comment_id': comment['id'],
                'body_char_length': len(body),
            },
        )

    return jsonify({'success': bool(comment), 'comment': comment})


@app.route('/other/api/request/<request_key>/send-email', methods=['POST'])
@staff_required
def api_send_email(request_key):
    """Send an email to the specified recipients."""
    data = request.get_json() or {}
    to_list = data.get('to_list', [])
    subject = data.get('subject', '').strip()
    body = data.get('body', '').strip()

    # Validate recipients
    if not isinstance(to_list, list) or not to_list:
        return jsonify({'success': False, 'error': 'At least one recipient is required'}), 400

    # Clean recipient list
    to_list = [email.strip() for email in to_list if email.strip()]
    if not to_list:
        return jsonify({'success': False, 'error': 'At least one valid email recipient is required'}), 400

    if not body:
        return jsonify({'success': False, 'error': 'Email body is required'}), 400

    # Default subject if not provided
    if not subject:
        req = database.get_request_by_key(request_key)
        subject = f"Re: {req.get('original_subject', 'Your Account Request')}" if req else 'Your Account Request'

    user = get_current_user()

    try:
        # Send the email
        notification_util.send_email(
            subject=subject,
            payload=body,
            to_list=to_list
        )

        # Log the sent email as a comment (activity stream)
        recipients_str = ', '.join(to_list)
        database.add_comment(
            request_key,
            author_email=user['email'],
            author_name=user['name'],
            body=f"Sent to: {recipients_str}\n\n{body}",
            comment_type='email_sent',
            email_subject=subject
        )

        # ── AUDIT: outbound email sent ───────────────────────────────────────
        audit.log_audit_event(
            actor_email=user['email'],
            action='request.email.send',
            target_type='request',
            target_id=request_key,
            details={
                'recipients': to_list,
                'subject': subject,
                'body_char_length': len(body),
            },
        )

        return jsonify({'success': True})

    except Exception as e:
        # ── AUDIT: email send failure ────────────────────────────────────────
        audit.log_audit_event(
            actor_email=user['email'],
            action='request.email.send',
            target_type='request',
            target_id=request_key,
            details={'recipients': to_list, 'subject': subject, 'error': str(e)},
            success=False,
        )
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# Webhook - Power Automate Integration
# =============================================================================

def parse_name_from_email(email):
    """
    Parse a display name from an email address.
    Handles formats like: firstname.lastname@domain.com -> Firstname Lastname
    """
    if not email:
        return 'Unknown'
    prefix = email.split('@')[0]
    # Split by common separators (., _, -)
    import re
    parts = re.split(r'[._-]', prefix)
    # Title case each part
    return ' '.join(part.capitalize() for part in parts if part)


@app.route('/other/api/webhook/new-request', methods=['POST'])
def webhook_new_request():
    """
    Webhook endpoint for Power Automate to send new email notifications.

    Supports conversation threading via Outlook's conversationId:
    - If conversationId matches an existing request, the email is added as a comment
    - If no match, a new request is created

    Expected payload:
    {
        "subject": "...",
        "body": "...",
        "from": "...",
        "receivedDateTime": "...",
        "messageId": "...",
        "conversationId": "..."  (optional but recommended for threading)
    }
    """
    # Simple API key auth (optional)
    api_key = request.headers.get('X-API-Key')
    expected_key = os.environ.get('WEBHOOK_API_KEY')
    if expected_key and api_key != expected_key:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}

    subject = data.get('subject', '')
    body = data.get('body', '')
    sender = data.get('from', '')
    message_id = data.get('messageId', '')
    conversation_id = data.get('conversationId', '')

    if not body:
        return jsonify({'success': False, 'error': 'Email body is required'}), 400

    # Check for duplicate by source_email_id first
    if message_id:
        existing = database.get_all_requests()
        for req in existing:
            if req.get('source_email_id') == message_id:
                return jsonify({
                    'success': True,
                    'message': 'Duplicate email, request already exists',
                    'request_key': req['request_key']
                })

    # Check for existing conversation - if found, add as comment (reply threading)
    if conversation_id:
        existing_request = database.get_request_by_conversation_id(conversation_id)
        if existing_request:
            sender_lower = (sender or '').lower()
            if sender_lower == existing_request.get('requester_email', '').lower():
                author_name = existing_request.get('requester_name') or parse_name_from_email(sender)
            else:
                author_name = database.get_staff_name(sender) or parse_name_from_email(sender)

            database.add_comment(
                existing_request['request_key'],
                author_email=sender or 'unknown@unknown.com',
                author_name=author_name,
                body=body,
                comment_type='email_received',
                email_subject=subject
            )
            return jsonify({
                'success': True,
                'message': 'Reply added to existing conversation',
                'request_key': existing_request['request_key'],
                'action': 'comment_added'
            })

    # No existing conversation - parse and create new request
    parsed = email_parser.parse_ilab_email(subject, body, sender)

    if not parsed['is_valid']:
        return jsonify({
            'success': False,
            'error': 'Could not parse valid request data from email'
        }), 400

    new_request = database.create_request(
        requester_email=parsed['requester_email'] or 'unknown@unknown.com',
        requester_name=parsed['requester_name'],
        organization=parsed['institution'],
        original_subject=subject,
        original_body=body,
        source_email_id=message_id,
        conversation_id=conversation_id or None,
        request_type='Account Request',
        ilab_link=parsed['ilab_link'],
        lab_name=parsed['lab_name']
    )

    return jsonify({
        'success': True,
        'request_key': new_request['request_key'],
        'message': f"Created request {new_request['request_key']}",
        'action': 'request_created'
    })


# =============================================================================
# Manual Import (Alternative to webhook)
# =============================================================================

@app.route('/other/import', methods=['GET', 'POST'])
@staff_required
def import_request():
    """Manually import a request by pasting email content."""
    if request.method == 'POST':
        subject = request.form.get('subject', '')
        body = request.form.get('body', '')

        parsed = email_parser.parse_ilab_email(subject, body)

        if not parsed['is_valid']:
            return render_template('import.html', error='Could not parse valid data from email')

        new_request = database.create_request(
            requester_email=parsed['requester_email'] or 'unknown@unknown.com',
            requester_name=parsed['requester_name'],
            organization=parsed['institution'],
            original_subject=subject,
            original_body=body,
            request_type='Account Request',
            ilab_link=parsed['ilab_link'],
            lab_name=parsed['lab_name']
        )

        user = get_current_user()
        # ── AUDIT: manual import ─────────────────────────────────────────────
        audit.log_audit_event(
            actor_email=user['email'],
            action='request.import.create',
            target_type='request',
            target_id=new_request['request_key'],
            details={
                'source': 'manual_import',
                'requester_email': new_request.get('requester_email'),
            },
        )

        return redirect(url_for('request_detail', request_key=new_request['request_key']))

    return render_template('import.html')


# =============================================================================
# Audit Log Viewer (Staff Only)
# =============================================================================

@app.route('/other/audit')
@staff_required
def audit_log_viewer():
    """
    Cross-request audit log viewer for staff.
    Supports filtering by agent and/or action category.
    """
    filter_agent = request.args.get('agent', '')
    filter_action = request.args.get('action_prefix', '')

    entries = audit.get_audit_log(
        actor_email=filter_agent if filter_agent else None,
        action_prefix=filter_action if filter_action else None,
        limit=300,
    )

    return render_template(
        'audit_log.html',
        entries=entries,
        staff_users=database.get_staff_users(),
        filter_agent=filter_agent,
        filter_action=filter_action,
    )


# =============================================================================
# Health Check (required by Docker / Azure App Service)
# =============================================================================

@app.route('/healthz')
def healthz():
    """Lightweight liveness probe used by the Docker HEALTHCHECK and Azure."""
    return jsonify({'status': 'ok'}), 200


# =============================================================================
# Error Handlers
# =============================================================================

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', message='Page not found'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', message='Internal server error'), 500


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    # Warn if using default secret key
    secret = os.environ.get('FLASK_SECRET_KEY', '')
    if not secret or 'dev-secret' in secret or 'change-in-prod' in secret:
        print('\n  ⚠️  WARNING: Using default secret key. Set FLASK_SECRET_KEY in .env for production.\n')

    database.init_db()
    app.run(debug=True, port=5006)
