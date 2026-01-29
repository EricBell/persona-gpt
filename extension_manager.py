# Copyright Polymorph Corporation (2026)

"""Manage extension requests for query limit increases."""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List

@dataclass
class ExtensionRequest:
    """Extension request data structure."""
    session_id: str
    email: str
    timestamp: str
    status: str  # 'pending', 'approved', 'denied'
    queries_granted: int = 0
    approved_at: Optional[str] = None
    request_id: str = ""  # session_id + timestamp hash for unique ID

def create_request(log_path: str, session_id: str, email: str) -> ExtensionRequest:
    """Create and log an extension request."""
    request = ExtensionRequest(
        session_id=session_id,
        email=email,
        timestamp=datetime.now().isoformat(),
        status='pending',
        request_id=f"{session_id}_{int(datetime.now().timestamp())}"
    )

    # Log to extension_requests.ndjson
    filename = os.path.join(log_path, 'extension_requests.ndjson')
    os.makedirs(log_path, exist_ok=True)

    with open(filename, 'a', encoding='utf-8') as f:
        f.write(json.dumps(asdict(request)) + '\n')

    return request

def get_pending_requests(log_path: str) -> List[ExtensionRequest]:
    """Retrieve all pending extension requests."""
    filename = os.path.join(log_path, 'extension_requests.ndjson')

    if not os.path.exists(filename):
        return []

    requests = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                if data['status'] == 'pending':
                    requests.append(ExtensionRequest(**data))

    # Sort by timestamp, newest first
    requests.sort(key=lambda r: r.timestamp, reverse=True)
    return requests

def get_all_requests(log_path: str, status_filter: str = 'all') -> List[ExtensionRequest]:
    """Retrieve extension requests filtered by status."""
    filename = os.path.join(log_path, 'extension_requests.ndjson')

    if not os.path.exists(filename):
        return []

    requests = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                if status_filter == 'all' or data['status'] == status_filter:
                    requests.append(ExtensionRequest(**data))

    # Sort by timestamp, newest first
    requests.sort(key=lambda r: r.timestamp, reverse=True)
    return requests

def get_request_by_id(log_path: str, request_id: str) -> Optional[ExtensionRequest]:
    """Get a specific request by ID."""
    filename = os.path.join(log_path, 'extension_requests.ndjson')

    if not os.path.exists(filename):
        return None

    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                if data['request_id'] == request_id:
                    return ExtensionRequest(**data)

    return None

def approve_request(log_path: str, request_id: str, queries_granted: int) -> None:
    """Mark request as approved and grant queries."""
    # Load all requests
    filename = os.path.join(log_path, 'extension_requests.ndjson')

    if not os.path.exists(filename):
        return

    requests = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                requests.append(json.loads(line))

    # Update the matching request
    for req in requests:
        if req['request_id'] == request_id:
            req['status'] = 'approved'
            req['queries_granted'] = queries_granted
            req['approved_at'] = datetime.now().isoformat()
            break

    # Write back all requests
    with open(filename, 'w', encoding='utf-8') as f:
        for req in requests:
            f.write(json.dumps(req) + '\n')

def deny_request(log_path: str, request_id: str) -> None:
    """Mark request as denied."""
    # Load all requests
    filename = os.path.join(log_path, 'extension_requests.ndjson')

    if not os.path.exists(filename):
        return

    requests = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                requests.append(json.loads(line))

    # Update the matching request
    for req in requests:
        if req['request_id'] == request_id:
            req['status'] = 'denied'
            req['approved_at'] = datetime.now().isoformat()
            break

    # Write back all requests
    with open(filename, 'w', encoding='utf-8') as f:
        for req in requests:
            f.write(json.dumps(req) + '\n')

def has_pending_request(log_path: str, session_id: str) -> bool:
    """Check if session already has a pending request."""
    filename = os.path.join(log_path, 'extension_requests.ndjson')

    if not os.path.exists(filename):
        return False

    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                if data['session_id'] == session_id and data['status'] == 'pending':
                    return True

    return False
