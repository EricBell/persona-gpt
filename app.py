# Copyright Polymorph Corporation (2026)

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import asdict
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from openai import OpenAI
from dotenv import load_dotenv

from version import __version__
from job_vetting import sanitize_job_description, evaluate_job_description
from query_logger import log_interaction
from config_validator import validate_flask_secret_key, validate_admin_reset_key
from intent_classifier import classify_intent, get_refusal_response, extract_company_names
from dataset_manager import parse_log_entries, validate_date_format
from email_detector import extract_email
from extension_manager import (
    create_request, has_pending_request, get_pending_requests,
    get_all_requests, get_request_by_id, approve_request, deny_request
)
from email_notifier import send_extension_request_notification

load_dotenv()

# Detect run mode early (before Flask app initialization)
is_local_mode = '--mode=local' in sys.argv

# Validate and set Flask secret key
flask_secret, flask_warning = validate_flask_secret_key(
    os.environ.get('FLASK_SECRET_KEY'),
    is_local_mode
)
if flask_warning:
    print(flask_warning, file=sys.stderr)

# Validate admin reset key if provided
admin_reset, admin_warning = validate_admin_reset_key(
    os.environ.get('ADMIN_RESET_KEY'),
    is_local_mode
)
if admin_warning:
    print(admin_warning, file=sys.stderr)

app = Flask(__name__)
app.secret_key = flask_secret

# Configuration
MAX_QUERIES_PER_SESSION = int(os.environ.get('MAX_QUERIES_PER_SESSION', 20))
MAX_QUERY_LENGTH = int(os.environ.get('MAX_QUERY_LENGTH', 500))
MAX_JOB_DESCRIPTION_LENGTH = int(os.environ.get('MAX_JOB_DESCRIPTION_LENGTH', 5000))
PERSONA_FILE_PATH = os.environ.get('PERSONA_FILE_PATH', './persona.txt')
QUERY_LOG_PATH = os.environ.get('QUERY_LOG_PATH', './logs')
ADMIN_RESET_KEY = admin_reset

# OpenAI client (lazy initialization)
_client = None

# Company names cache (lazy initialization)
_company_names_cache = None


def get_openai_client():
    """Get or create OpenAI client."""
    global _client
    if _client is None:
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        _client = OpenAI(api_key=api_key)
    return _client


def get_company_names():
    """Get cached company names from persona file."""
    global _company_names_cache
    if _company_names_cache is None:
        _company_names_cache = extract_company_names(PERSONA_FILE_PATH)
    return _company_names_cache


def load_persona():
    """Load persona instructions from file. Re-reads on each call for hot-swapping."""
    try:
        with open(PERSONA_FILE_PATH, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "You are a helpful assistant representing Eric Bell."


def sanitize_input(user_input):
    """Sanitize user input to prevent prompt injection."""
    if not user_input:
        return ""

    # Truncate to max length
    user_input = user_input[:MAX_QUERY_LENGTH]

    # Remove potential injection patterns
    # Strip attempts to override system instructions
    patterns_to_remove = [
        r'(?i)ignore\s+(all\s+)?(previous|above|prior)\s+instructions?',
        r'(?i)forget\s+(all\s+)?(previous|above|prior)\s+instructions?',
        r'(?i)disregard\s+(all\s+)?(previous|above|prior)\s+instructions?',
        r'(?i)you\s+are\s+now\s+',
        r'(?i)act\s+as\s+(if\s+you\s+are\s+)?',
        r'(?i)pretend\s+(to\s+be|you\s+are)\s+',
        r'(?i)system\s*:\s*',
        r'(?i)assistant\s*:\s*',
        r'(?i)user\s*:\s*',
    ]

    for pattern in patterns_to_remove:
        user_input = re.sub(pattern, '', user_input)

    return user_input.strip()


def get_query_count():
    """Get current query count from session."""
    return session.get('query_count', 0)


def increment_query_count():
    """Increment and return query count."""
    count = get_query_count() + 1
    session['query_count'] = count
    return count


def get_conversation_history():
    """Get conversation history from session."""
    return session.get('conversation', [])


def add_to_conversation(role, content):
    """Add a message to conversation history."""
    conversation = get_conversation_history()
    conversation.append({'role': role, 'content': content})
    # Keep last 20 messages to prevent context from growing too large
    session['conversation'] = conversation[-20:]


def get_session_id():
    """Get or create a unique session ID."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())[:8]
    return session['session_id']


def get_max_queries_for_session():
    """Get max queries for current session (base + approved extensions)."""
    base_max = MAX_QUERIES_PER_SESSION

    # Check if this session has approved extension
    session_id = get_session_id()
    approvals_file = os.path.join(QUERY_LOG_PATH, 'approved_extensions.json')

    if os.path.exists(approvals_file):
        try:
            with open(approvals_file, 'r', encoding='utf-8') as f:
                approvals = json.load(f)

            if session_id in approvals:
                # Extension approved, add granted queries
                granted = approvals[session_id]['queries_granted']
                return base_max + granted
        except Exception:
            # If file is corrupted, just return base max
            pass

    return base_max


@app.route('/')
def index():
    """Render the chat interface."""
    max_queries = get_max_queries_for_session()
    return render_template('index.html',
                         query_count=get_query_count(),
                         max_queries=max_queries,
                         max_query_length=MAX_QUERY_LENGTH,
                         max_job_description_length=MAX_JOB_DESCRIPTION_LENGTH,
                         version=__version__)


@app.route('/health')
def health():
    """Health check endpoint for container monitoring."""
    return jsonify({'status': 'healthy', 'version': __version__}), 200


@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages."""
    # Check query limit (with extension support)
    current_count = get_query_count()
    max_queries = get_max_queries_for_session()

    if current_count >= max_queries:
        # Get and validate input first (to check for email)
        data = request.get_json()
        if data and 'message' in data:
            user_message = data.get('message', '').strip()

            # Check if user is submitting email for extension request
            email = extract_email(user_message)

            if email and not has_pending_request(QUERY_LOG_PATH, get_session_id()):
                # Create extension request
                ext_request = create_request(QUERY_LOG_PATH, get_session_id(), email)

                # Send notification to Eric
                smtp_config = {
                    'host': os.environ.get('SMTP_HOST'),
                    'port': int(os.environ.get('SMTP_PORT', 587)),
                    'use_tls': os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true',
                    'username': os.environ.get('SMTP_USERNAME'),
                    'password': os.environ.get('SMTP_PASSWORD'),
                    'from_email': os.environ.get('SMTP_USERNAME')
                }

                admin_email = os.environ.get('ADMIN_EMAIL')
                admin_url = os.environ.get('APP_URL', request.host_url.rstrip('/'))

                # Send email notification (best-effort, don't fail if email fails)
                try:
                    send_extension_request_notification(
                        ext_request.request_id,
                        get_session_id(),
                        email,
                        admin_email,
                        admin_url,
                        smtp_config
                    )
                except Exception as e:
                    # Log error but continue
                    print(f"Email notification failed: {e}", file=sys.stderr)

                # Mark request in session to prevent re-submission
                session['extension_requested'] = True
                session['extension_request_id'] = ext_request.request_id

                return jsonify({
                    'error': 'limit_reached',
                    'extension_requested': True,
                    'message': 'Extension request received! We\'ll review your request and may extend your session. Check back shortly.',
                    'query_count': current_count,
                    'max_queries': max_queries
                }), 429

        # Default limit reached message (no email detected or already requested)
        if session.get('extension_requested'):
            message = 'Your extension request is pending review. Please check back later.'
        else:
            message = f'You have reached the maximum of {max_queries} questions for this session. To request more questions, send a message with your email address.'

        return jsonify({
            'error': 'limit_reached',
            'message': message,
            'query_count': current_count,
            'max_queries': max_queries
        }), 429

    # Get and validate input
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'No message provided'}), 400

    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'error': 'Empty message'}), 400

    # Sanitize input
    user_message = sanitize_input(user_message)
    if not user_message:
        return jsonify({'error': 'Invalid message'}), 400

    # Check length after sanitization
    if len(user_message) > MAX_QUERY_LENGTH:
        return jsonify({
            'error': 'Message too long',
            'max_length': MAX_QUERY_LENGTH
        }), 400

    # LLM-based intent classification
    try:
        client = get_openai_client()
        company_names = get_company_names()
        scope = classify_intent(client, user_message, company_names)

        if scope == 'OUT_OF_SCOPE':
            # Return canned response without full conversation
            refusal_message = get_refusal_response()

            # Log the filtered interaction
            log_interaction(
                QUERY_LOG_PATH,
                get_session_id(),
                user_message,
                refusal_message,
                filtered_pre_llm=True
            )

            # Increment query count (prevent abuse)
            new_count = increment_query_count()

            max_queries = get_max_queries_for_session()
            return jsonify({
                'response': refusal_message,
                'query_count': new_count,
                'max_queries': max_queries,
                'queries_remaining': max_queries - new_count,
                'filtered_pre_llm': True
            })

    except Exception as e:
        # Classification failed - log and continue to main LLM (safe fallback)
        print(f"Classification error: {e}", file=sys.stderr)
        # Fall through to main conversation

    # IN_SCOPE or classification failed - proceed with full conversation
    try:
        # Load persona (re-read each time for hot-swapping)
        persona = load_persona()

        # Add user message to history
        add_to_conversation('user', user_message)

        # Build messages for API call
        messages = [{'role': 'system', 'content': persona}]
        messages.extend(get_conversation_history())

        # Call OpenAI API
        client = get_openai_client()
        response = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )

        assistant_message = response.choices[0].message.content

        # Log the interaction
        log_interaction(
            QUERY_LOG_PATH,
            get_session_id(),
            user_message,
            assistant_message,
            filtered_pre_llm=False
        )

        # Add assistant response to history
        add_to_conversation('assistant', assistant_message)

        # Increment query count
        new_count = increment_query_count()

        max_queries = get_max_queries_for_session()
        return jsonify({
            'response': assistant_message,
            'query_count': new_count,
            'max_queries': max_queries,
            'queries_remaining': max_queries - new_count
        })

    except Exception as e:
        return jsonify({
            'error': 'Failed to get response',
            'message': str(e)
        }), 500


@app.route('/vet', methods=['POST'])
def vet():
    """Evaluate a job description against the persona."""
    # Get and validate input
    data = request.get_json()
    if not data or 'job_description' not in data:
        return jsonify({'error': 'No job description provided'}), 400

    job_description = data.get('job_description', '').strip()
    if not job_description:
        return jsonify({'error': 'Empty job description'}), 400

    # Sanitize input
    job_description = sanitize_job_description(job_description, MAX_JOB_DESCRIPTION_LENGTH)
    if not job_description:
        return jsonify({'error': 'Invalid job description'}), 400

    try:
        # Load persona
        persona = load_persona()

        # Get OpenAI client and evaluate
        client = get_openai_client()
        result = evaluate_job_description(client, job_description, persona)

        return jsonify(asdict(result))

    except Exception as e:
        return jsonify({
            'error': 'Failed to evaluate job description',
            'message': str(e)
        }), 500


@app.route('/status')
def status():
    """Get current session status."""
    max_queries = get_max_queries_for_session()
    query_count = get_query_count()
    return jsonify({
        'query_count': query_count,
        'max_queries': max_queries,
        'queries_remaining': max_queries - query_count,
        'version': __version__
    })


@app.route('/reset')
def reset():
    """Admin endpoint to reset session. Requires ADMIN_RESET_KEY."""
    if not ADMIN_RESET_KEY:
        return jsonify({'error': 'Reset endpoint not configured'}), 403

    key = request.args.get('key', '')
    if key != ADMIN_RESET_KEY:
        return jsonify({'error': 'Invalid key'}), 403

    # Clear session data
    old_count = get_query_count()
    session.clear()

    return jsonify({
        'status': 'success',
        'message': 'Session reset successfully',
        'previous_query_count': old_count
    })


@app.route('/dataset')
def dataset():
    """Admin endpoint to view conversation logs. Requires ADMIN_RESET_KEY."""
    if not ADMIN_RESET_KEY:
        return jsonify({'error': 'Dataset endpoint not configured'}), 403

    key = request.args.get('key', '')
    if key != ADMIN_RESET_KEY:
        return jsonify({'error': 'Invalid key'}), 403

    # Parse query parameters
    date = request.args.get('date', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    session_id = request.args.get('session_id', '').strip()
    filtered = request.args.get('filtered', 'all').strip()
    response_format = request.args.get('format', 'html').strip().lower()

    # Handle pagination
    try:
        limit = int(request.args.get('limit', 100))
    except ValueError:
        limit = 100

    try:
        offset = int(request.args.get('offset', 0))
    except ValueError:
        offset = 0

    # Handle date parameter (overrides start_date/end_date)
    if date:
        if not validate_date_format(date):
            error_msg = f'Invalid date format: {date}. Use YYMMDD, "today", or "yesterday".'
            if response_format == 'json':
                return jsonify({'error': error_msg}), 400
            return render_template('dataset.html', error=error_msg, key=key, filters={})

        start_date = date
        end_date = date
    else:
        # Validate date formats if provided
        if start_date and not validate_date_format(start_date):
            error_msg = f'Invalid start_date format: {start_date}. Use YYMMDD, "today", or "yesterday".'
            if response_format == 'json':
                return jsonify({'error': error_msg}), 400
            return render_template('dataset.html', error=error_msg, key=key, filters={})

        if end_date and not validate_date_format(end_date):
            error_msg = f'Invalid end_date format: {end_date}. Use YYMMDD, "today", or "yesterday".'
            if response_format == 'json':
                return jsonify({'error': error_msg}), 400
            return render_template('dataset.html', error=error_msg, key=key, filters={})

    # Validate filtered parameter
    if filtered not in ['all', 'true', 'false']:
        error_msg = 'Invalid filtered parameter. Use "all", "true", or "false".'
        if response_format == 'json':
            return jsonify({'error': error_msg}), 400
        return render_template('dataset.html', error=error_msg, key=key, filters={})

    # Parse log entries
    try:
        result = parse_log_entries(
            log_path=QUERY_LOG_PATH,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            session_id=session_id if session_id else None,
            filtered=filtered,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        error_msg = f'Error parsing logs: {str(e)}'
        if response_format == 'json':
            return jsonify({'error': error_msg}), 500
        return render_template('dataset.html', error=error_msg, key=key, filters={})

    # Return JSON format if requested
    if response_format == 'json':
        return jsonify(result)

    # Return HTML format
    return render_template(
        'dataset.html',
        entries=result['entries'],
        total=result['total'],
        limit=result['limit'],
        offset=result['offset'],
        has_more=result['has_more'],
        filters={
            'date': date,
            'start_date': start_date,
            'end_date': end_date,
            'session_id': session_id,
            'filtered': filtered
        },
        key=key  # Pass key for pagination links
    )


@app.route('/extension-requests')
def extension_requests():
    """Admin page to review and approve extension requests."""
    if not ADMIN_RESET_KEY:
        return jsonify({'error': 'Extension requests endpoint not configured'}), 403

    key = request.args.get('key', '')
    if key != ADMIN_RESET_KEY:
        return jsonify({'error': 'Invalid key'}), 403

    # Get filter parameters
    status_filter = request.args.get('status', 'pending')  # pending, approved, denied, all

    if status_filter == 'pending':
        requests = get_pending_requests(QUERY_LOG_PATH)
    else:
        requests = get_all_requests(QUERY_LOG_PATH, status_filter)

    return render_template(
        'extension_requests.html',
        requests=requests,
        key=key,
        status_filter=status_filter
    )


@app.route('/approve-extension', methods=['POST'])
def approve_extension():
    """Approve an extension request and grant queries to session."""
    if not ADMIN_RESET_KEY:
        return jsonify({'error': 'Extension approval not configured'}), 403

    data = request.get_json()
    key = data.get('key', '')
    if key != ADMIN_RESET_KEY:
        return jsonify({'error': 'Invalid key'}), 403

    request_id = data.get('request_id')
    queries_granted = int(data.get('queries_granted', 10))

    # Get request details
    ext_request = get_request_by_id(QUERY_LOG_PATH, request_id)
    if not ext_request:
        return jsonify({'error': 'Request not found'}), 404

    # Mark as approved
    approve_request(QUERY_LOG_PATH, request_id, queries_granted)

    # Store approval in separate tracking file for session lookup
    approvals_file = os.path.join(QUERY_LOG_PATH, 'approved_extensions.json')
    os.makedirs(QUERY_LOG_PATH, exist_ok=True)

    # Load existing approvals
    if os.path.exists(approvals_file):
        try:
            with open(approvals_file, 'r', encoding='utf-8') as f:
                approvals = json.load(f)
        except Exception:
            approvals = {}
    else:
        approvals = {}

    # Add approval (keyed by session_id)
    approvals[ext_request.session_id] = {
        'queries_granted': queries_granted,
        'approved_at': datetime.now().isoformat(),
        'request_id': request_id,
        'email': ext_request.email
    }

    # Save
    with open(approvals_file, 'w', encoding='utf-8') as f:
        json.dump(approvals, f, indent=2)

    return jsonify({
        'status': 'success',
        'message': f'Extension approved: {queries_granted} additional queries granted',
        'session_id': ext_request.session_id
    })


@app.route('/deny-extension', methods=['POST'])
def deny_extension():
    """Deny an extension request."""
    if not ADMIN_RESET_KEY:
        return jsonify({'error': 'Extension denial not configured'}), 403

    data = request.get_json()
    key = data.get('key', '')
    if key != ADMIN_RESET_KEY:
        return jsonify({'error': 'Invalid key'}), 403

    request_id = data.get('request_id')

    # Get request details
    ext_request = get_request_by_id(QUERY_LOG_PATH, request_id)
    if not ext_request:
        return jsonify({'error': 'Request not found'}), 404

    # Mark as denied
    deny_request(QUERY_LOG_PATH, request_id)

    return jsonify({
        'status': 'success',
        'message': 'Extension request denied',
        'session_id': ext_request.session_id
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ProfileGPT - Ask Eric AI')
    parser.add_argument('--mode', choices=['local', 'container'], default='local',
                       help='Run mode: local (Flask dev server) or container (for Gunicorn)')
    args = parser.parse_args()

    if args.mode == 'local':
        # Local development mode
        port = int(os.environ.get('PORT', 5000))
        app.run(debug=True, host='0.0.0.0', port=port)
    else:
        # Container mode - just print info, Gunicorn handles the serving
        print("Container mode: Use Gunicorn to run the application")
        print("Example: gunicorn -b 0.0.0.0:5000 app:app")
