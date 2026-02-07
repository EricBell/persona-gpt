# Usage Tracking Feature

## Overview

ProfileGPT now includes comprehensive usage tracking for all OpenAI API calls. This feature automatically logs token usage and calculates costs, providing visibility into API spending and helping optimize the application.

## What's Tracked

Every OpenAI API call is logged with the following information:

- **Session ID** - Identifies which user session made the call
- **Timestamp** - ISO format timestamp (YYYY-MM-DDTHH:MM:SS)
- **Token Counts**:
  - `prompt_tokens` - Input tokens sent to OpenAI
  - `completion_tokens` - Output tokens received from OpenAI
  - `total_tokens` - Sum of input and output tokens
- **Model** - Which model was used (e.g., `gpt-4o-mini`)
- **Call Type** - Purpose of the API call:
  - `classification` - Intent classification (IN_SCOPE vs OUT_OF_SCOPE)
  - `conversation` - Main chat conversation
  - `job_vetting` - Job description analysis
- **Scope** - Query classification (IN_SCOPE, OUT_OF_SCOPE, or none)
- **Costs**:
  - `input_cost` - Cost for input tokens
  - `output_cost` - Cost for output tokens
  - `total_cost` - Total cost for the API call

## Pricing

Costs are calculated using gpt-4o-mini pricing (as of January 2026):
- **Input tokens**: $0.150 per 1M tokens
- **Output tokens**: $0.600 per 1M tokens

## Data Storage

Usage logs are stored in NDJSON (newline-delimited JSON) format:

**File**: `logs/usage_tracking.ndjson`

Each line is a complete JSON object representing one API call.

**Example record**:
```json
{
  "session_id": "a1b2c3d4",
  "timestamp": "2026-02-07T14:30:15.123456",
  "prompt_tokens": 250,
  "completion_tokens": 150,
  "total_tokens": 400,
  "model": "gpt-4o-mini",
  "call_type": "conversation",
  "scope": "IN_SCOPE",
  "input_cost": 0.0000375,
  "output_cost": 0.0000900,
  "total_cost": 0.0001275
}
```

## Admin Dashboard

### Accessing the Dashboard

Visit: `https://your-domain.com/usage-stats?key=YOUR_ADMIN_KEY`

The dashboard requires the `ADMIN_RESET_KEY` environment variable to be set.

### Dashboard Features

**Overview Statistics**:
- Total API calls made
- Total tokens consumed
- Total cost (USD)
- Average tokens per call
- Average cost per call

**Breakdown by Call Type**:
- See usage and costs for classification vs conversation vs job_vetting
- Identify which features consume the most tokens

**Breakdown by Scope**:
- Compare IN_SCOPE vs OUT_OF_SCOPE query costs
- Validate that intent classification saves tokens

**Daily Usage**:
- View usage trends by date
- Identify peak usage days
- Track spending over time

**Most Expensive Sessions**:
- Identify sessions that consumed the most tokens
- Useful for detecting unusual usage patterns
- Shows last 30 days by default

### Filtering

Apply filters to analyze specific data:

- **Date Range**: Filter by start_date and end_date (YYYY-MM-DD format)
- **Session ID**: View usage for a specific session
- **Format**: Use `?format=json` to get raw JSON data

**Example URLs**:
```
# View all usage
/usage-stats?key=YOUR_KEY

# Filter by date
/usage-stats?key=YOUR_KEY&start_date=2026-02-01&end_date=2026-02-07

# View specific session
/usage-stats?key=YOUR_KEY&session_id=a1b2c3d4

# Get JSON format
/usage-stats?key=YOUR_KEY&format=json
```

## Programmatic Access

You can also access usage data programmatically:

```python
from usage_tracker import parse_usage_logs, calculate_usage_stats

# Load all usage records
records = parse_usage_logs('./logs')

# Filter by date range
records = parse_usage_logs(
    './logs',
    start_date='2026-02-01',
    end_date='2026-02-07'
)

# Calculate statistics
stats = calculate_usage_stats(records)
print(f"Total cost: ${stats['total_cost']:.4f}")
print(f"Total tokens: {stats['total_tokens']:,}")

# Get expensive sessions
from usage_tracker import get_recent_expensive_sessions
expensive = get_recent_expensive_sessions('./logs', limit=5, days=7)
for session in expensive:
    print(f"Session {session['session_id']}: ${session['total_cost']:.4f}")
```

## Use Cases

### 1. Cost Monitoring
Track your OpenAI spending in real-time and set budgets:

```python
# Check if today's spending exceeds budget
from datetime import datetime
from usage_tracker import parse_usage_logs, calculate_usage_stats

today = datetime.now().strftime('%Y-%m-%d')
records = parse_usage_logs('./logs', start_date=today, end_date=today)
stats = calculate_usage_stats(records)

DAILY_BUDGET = 5.00  # $5 per day
if stats['total_cost'] > DAILY_BUDGET:
    print(f"⚠️ Budget exceeded! Spent ${stats['total_cost']:.2f} today")
```

### 2. Optimization Validation
Prove that your optimizations (like conversation_history_limit) save money:

```python
# Compare token usage before and after optimization
before = parse_usage_logs('./logs', start_date='2026-01-01', end_date='2026-01-15')
after = parse_usage_logs('./logs', start_date='2026-01-16', end_date='2026-01-31')

before_stats = calculate_usage_stats(before)
after_stats = calculate_usage_stats(after)

before_avg = before_stats['average_tokens_per_call']
after_avg = after_stats['average_tokens_per_call']
savings = ((before_avg - after_avg) / before_avg) * 100

print(f"Token reduction: {savings:.1f}%")
print(f"Cost savings: ${(before_stats['average_cost_per_call'] - after_stats['average_cost_per_call']):.6f} per call")
```

### 3. Classification Effectiveness
Measure how much money intent classification saves:

```python
stats = calculate_usage_stats(parse_usage_logs('./logs'))

classification_cost = stats['by_call_type'].get('classification', {}).get('cost', 0)
conversation_cost = stats['by_call_type'].get('conversation', {}).get('cost', 0)
total_cost = stats['total_cost']

# If classification filtered out queries, we saved (500 - 10) tokens per filtered query
out_of_scope_count = stats['by_scope'].get('OUT_OF_SCOPE', {}).get('count', 0)
tokens_saved_per_filtered = 490  # Rough estimate (500 conversation - 10 classification)
estimated_savings = out_of_scope_count * tokens_saved_per_filtered * 0.000150  # Input token cost

print(f"Estimated savings from filtering: ${estimated_savings:.2f}")
print(f"Classification overhead: ${classification_cost:.2f}")
print(f"Net benefit: ${(estimated_savings - classification_cost):.2f}")
```

### 4. Budget Forecasting
Project monthly costs based on current usage:

```python
from datetime import datetime, timedelta

# Get last 7 days of usage
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

records = parse_usage_logs(
    './logs',
    start_date=start_date.strftime('%Y-%m-%d'),
    end_date=end_date.strftime('%Y-%m-%d')
)
stats = calculate_usage_stats(records)

daily_avg = stats['total_cost'] / 7
monthly_projection = daily_avg * 30

print(f"Average daily cost: ${daily_avg:.2f}")
print(f"Projected monthly cost: ${monthly_projection:.2f}")
```

## Integration with Existing Systems

The usage tracking system is automatically integrated into:

- **Chat endpoint** (`/chat`) - Logs both classification and conversation calls
- **Job vetting endpoint** (`/vet`) - Logs job description analysis calls
- **All OpenAI API calls** - No configuration needed

## Environment Variables

No additional environment variables are required. The feature uses existing paths:

- `QUERY_LOG_PATH` - Directory where usage logs are stored (default: `./logs`)
- `ADMIN_RESET_KEY` - Required to access the admin dashboard

## Files Added

- `usage_tracker.py` - Core usage tracking module
- `templates/usage_stats.html` - Admin dashboard template
- `logs/usage_tracking.ndjson` - Usage log file (created automatically)

## API Changes

### Breaking Changes
None. The feature is backward compatible.

### New Functions
- `log_usage()` - Log an API call's token usage
- `parse_usage_logs()` - Load and filter usage records
- `calculate_usage_stats()` - Calculate aggregate statistics
- `get_recent_expensive_sessions()` - Find most expensive sessions

### Modified Functions
- `evaluate_job_description()` - Now returns `(VettingResult, usage)` tuple instead of just `VettingResult`

## Future Enhancements

Potential improvements:

1. **Budget Alerts** - Email notifications when spending exceeds thresholds
2. **Real-time Dashboard** - WebSocket-based live usage monitoring
3. **Cost Attribution** - Tag sessions by source (recruiter, company, etc.)
4. **Historical Trends** - Graph usage over weeks/months
5. **OpenAI Usage API Integration** - Fetch official billing data for reconciliation
6. **Cost Predictions** - ML-based forecasting of future usage
7. **Rate Limiting by Cost** - Throttle requests when budget exceeded

## Version History

- **v0.13.0** - Initial release of usage tracking feature
