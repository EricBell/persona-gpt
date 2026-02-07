# Copyright Polymorph Corporation (2026)

"""
Usage tracking for OpenAI API calls.

Tracks token usage and costs per request, provides analytics.
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


# GPT-4o-mini pricing (as of January 2026)
# Source: https://openai.com/api/pricing/
COST_PER_1M_INPUT_TOKENS = 0.150  # $0.150 per 1M tokens
COST_PER_1M_OUTPUT_TOKENS = 0.600  # $0.600 per 1M tokens


@dataclass
class UsageRecord:
    """Token usage record for a single API call."""
    session_id: str
    timestamp: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    call_type: str  # 'classification', 'conversation', 'job_vetting'
    scope: Optional[str]  # 'IN_SCOPE', 'OUT_OF_SCOPE', or None
    input_cost: float
    output_cost: float
    total_cost: float


def calculate_cost(prompt_tokens: int, completion_tokens: int) -> tuple[float, float, float]:
    """
    Calculate cost for token usage.

    Args:
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens

    Returns:
        Tuple of (input_cost, output_cost, total_cost) in USD
    """
    input_cost = (prompt_tokens / 1_000_000) * COST_PER_1M_INPUT_TOKENS
    output_cost = (completion_tokens / 1_000_000) * COST_PER_1M_OUTPUT_TOKENS
    total_cost = input_cost + output_cost

    return input_cost, output_cost, total_cost


def log_usage(
    log_path: str,
    session_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    model: str,
    call_type: str,
    scope: Optional[str] = None
) -> UsageRecord:
    """
    Log usage data for an OpenAI API call.

    Args:
        log_path: Directory to write usage logs
        session_id: Session identifier
        prompt_tokens: Input tokens used
        completion_tokens: Output tokens used
        total_tokens: Total tokens used
        model: Model name (e.g., 'gpt-4o-mini')
        call_type: Type of call ('classification', 'conversation', 'job_vetting')
        scope: Query scope ('IN_SCOPE', 'OUT_OF_SCOPE', or None)

    Returns:
        UsageRecord object
    """
    input_cost, output_cost, total_cost = calculate_cost(prompt_tokens, completion_tokens)

    record = UsageRecord(
        session_id=session_id,
        timestamp=datetime.now().isoformat(),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=model,
        call_type=call_type,
        scope=scope,
        input_cost=input_cost,
        output_cost=output_cost,
        total_cost=total_cost
    )

    # Write to NDJSON log file
    filename = os.path.join(log_path, 'usage_tracking.ndjson')
    os.makedirs(log_path, exist_ok=True)

    with open(filename, 'a', encoding='utf-8') as f:
        f.write(json.dumps(asdict(record)) + '\n')

    return record


def parse_usage_logs(
    log_path: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    session_id: Optional[str] = None
) -> List[UsageRecord]:
    """
    Parse usage logs with optional filters.

    Args:
        log_path: Directory containing usage logs
        start_date: ISO format date string (YYYY-MM-DD) or None
        end_date: ISO format date string (YYYY-MM-DD) or None
        session_id: Filter by session ID or None

    Returns:
        List of UsageRecord objects
    """
    filename = os.path.join(log_path, 'usage_tracking.ndjson')

    if not os.path.exists(filename):
        return []

    records = []

    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue

            data = json.loads(line)
            record = UsageRecord(**data)

            # Apply filters
            if start_date:
                record_date = record.timestamp[:10]  # Extract YYYY-MM-DD
                if record_date < start_date:
                    continue

            if end_date:
                record_date = record.timestamp[:10]
                if record_date > end_date:
                    continue

            if session_id and record.session_id != session_id:
                continue

            records.append(record)

    return records


def calculate_usage_stats(records: List[UsageRecord]) -> Dict[str, Any]:
    """
    Calculate aggregate statistics from usage records.

    Args:
        records: List of UsageRecord objects

    Returns:
        Dictionary with aggregate statistics
    """
    if not records:
        return {
            'total_records': 0,
            'total_tokens': 0,
            'total_cost': 0.0,
            'by_call_type': {},
            'by_scope': {},
            'by_model': {},
            'by_date': {},
            'average_tokens_per_call': 0,
            'average_cost_per_call': 0.0
        }

    total_tokens = sum(r.total_tokens for r in records)
    total_cost = sum(r.total_cost for r in records)

    # Group by call type
    by_call_type = {}
    for record in records:
        if record.call_type not in by_call_type:
            by_call_type[record.call_type] = {
                'count': 0,
                'tokens': 0,
                'cost': 0.0
            }
        by_call_type[record.call_type]['count'] += 1
        by_call_type[record.call_type]['tokens'] += record.total_tokens
        by_call_type[record.call_type]['cost'] += record.total_cost

    # Group by scope
    by_scope = {}
    for record in records:
        scope = record.scope or 'none'
        if scope not in by_scope:
            by_scope[scope] = {
                'count': 0,
                'tokens': 0,
                'cost': 0.0
            }
        by_scope[scope]['count'] += 1
        by_scope[scope]['tokens'] += record.total_tokens
        by_scope[scope]['cost'] += record.total_cost

    # Group by model
    by_model = {}
    for record in records:
        if record.model not in by_model:
            by_model[record.model] = {
                'count': 0,
                'tokens': 0,
                'cost': 0.0
            }
        by_model[record.model]['count'] += 1
        by_model[record.model]['tokens'] += record.total_tokens
        by_model[record.model]['cost'] += record.total_cost

    # Group by date
    by_date = {}
    for record in records:
        date = record.timestamp[:10]  # Extract YYYY-MM-DD
        if date not in by_date:
            by_date[date] = {
                'count': 0,
                'tokens': 0,
                'cost': 0.0
            }
        by_date[date]['count'] += 1
        by_date[date]['tokens'] += record.total_tokens
        by_date[date]['cost'] += record.total_cost

    return {
        'total_records': len(records),
        'total_tokens': total_tokens,
        'total_cost': total_cost,
        'by_call_type': by_call_type,
        'by_scope': by_scope,
        'by_model': by_model,
        'by_date': sorted(by_date.items(), reverse=True),  # Most recent first
        'average_tokens_per_call': total_tokens / len(records),
        'average_cost_per_call': total_cost / len(records)
    }


def get_recent_expensive_sessions(
    log_path: str,
    limit: int = 10,
    days: int = 7
) -> List[Dict[str, Any]]:
    """
    Get most expensive sessions from recent days.

    Args:
        log_path: Directory containing usage logs
        limit: Maximum number of sessions to return
        days: Number of days to look back

    Returns:
        List of session summaries sorted by cost (descending)
    """
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    records = parse_usage_logs(log_path, start_date=cutoff_date)

    # Group by session
    sessions = {}
    for record in records:
        if record.session_id not in sessions:
            sessions[record.session_id] = {
                'session_id': record.session_id,
                'total_calls': 0,
                'total_tokens': 0,
                'total_cost': 0.0,
                'first_seen': record.timestamp,
                'last_seen': record.timestamp
            }

        session = sessions[record.session_id]
        session['total_calls'] += 1
        session['total_tokens'] += record.total_tokens
        session['total_cost'] += record.total_cost
        session['last_seen'] = record.timestamp

    # Sort by cost and return top N
    sorted_sessions = sorted(sessions.values(), key=lambda s: s['total_cost'], reverse=True)
    return sorted_sessions[:limit]
