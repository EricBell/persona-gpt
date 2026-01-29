# Query Limit Extension Request System - Implementation Summary

## Version
- **Version Updated**: 0.9.1 → 0.10.0 (MINOR increment for new feature)
- **Date**: 2026-01-29

## Overview
Implemented a complete system allowing users to request additional chat queries when they reach their session limit. Eric receives email notifications and can approve/deny requests via an admin UI.

## Files Created

### 1. `email_detector.py`
- Email extraction from user messages using regex
- Email validation functionality
- Exports: `extract_email()`, `is_valid_email()`

### 2. `extension_manager.py`
- Extension request data structure (`ExtensionRequest` dataclass)
- CRUD operations for extension requests
- Request storage in NDJSON format
- Session-based approval tracking
- Exports: `create_request()`, `get_pending_requests()`, `approve_request()`, `deny_request()`, etc.

### 3. `email_notifier.py`
- SMTP email notification system
- Sends alerts to admin when extension requests are created
- Exports: `send_extension_request_notification()`

### 4. `templates/extension_requests.html`
- Admin UI for reviewing extension requests
- Filter tabs: Pending / Approved / Denied / All
- Approve/Deny action buttons
- Modal for specifying query grant amount
- Matches design of existing `dataset.html` page

## Files Modified

### 1. `app.py`
**New Imports:**
- `email_detector`, `extension_manager`, `email_notifier` modules
- `json`, `datetime` for data handling

**New Functions:**
- `get_max_queries_for_session()` - Calculates session limit including approved extensions

**Modified Routes:**
- `/` - Uses `get_max_queries_for_session()` instead of constant
- `/chat` - Extension request detection and handling
- `/status` - Returns dynamic max_queries

**New Routes:**
- `/extension-requests` - Admin UI for managing requests
- `/approve-extension` - API endpoint to approve requests
- `/deny-extension` - API endpoint to deny requests

### 2. `static/js/main.js`
**Modified:**
- `sendMessage()` function now handles `extension_requested` responses
- Updates `config.maxQueries` dynamically when extensions are approved
- Shows appropriate messages based on extension request status

### 3. `Dockerfile`
**Added:**
- `COPY email_detector.py .`
- `COPY extension_manager.py .`
- `COPY email_notifier.py .`

### 4. `.env.example`
**Added:**
- `ADMIN_EMAIL` - Admin email for notifications
- `APP_URL` - Application URL for email links
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS` - SMTP server config
- `SMTP_USERNAME`, `SMTP_PASSWORD` - SMTP credentials

### 5. `version.py` & `pyproject.toml`
- Version bumped to `0.10.0`

### 6. `CLAUDE.md`
- Added "Query Limit Extension Requests" section
- Documented user flow, admin workflow, environment variables, and key files

## User Flow

1. **Hit Limit**
   - User reaches 20/20 queries
   - Message: "You have reached the maximum of 20 questions for this session. To request more questions, send a message with your email address."

2. **Submit Email**
   - User types: "recruiter@company.com"
   - System extracts email, creates request
   - Sends notification to `ADMIN_EMAIL`
   - User sees: "Extension request received! We'll review your request and may extend your session. Check back shortly."

3. **Pending State**
   - Subsequent limit messages show: "Your extension request is pending review. Please check back later."
   - Prevents duplicate requests

4. **Admin Approval**
   - Eric visits `/extension-requests?key=YOUR_KEY`
   - Sees pending request with email, session ID, timestamp
   - Clicks "Approve", specifies queries to grant (default: 10)
   - Request marked as approved

5. **Session Extended**
   - User refreshes page or submits query
   - New limit: 30 queries (20 base + 10 granted)
   - Query count shows: "20/30"
   - User can continue chatting

## Data Storage

### `logs/extension_requests.ndjson`
```json
{"session_id": "abc12345", "email": "test@example.com", "timestamp": "2026-01-29T10:30:00", "status": "pending", "queries_granted": 0, "approved_at": null, "request_id": "abc12345_1738155000"}
{"session_id": "abc12345", "email": "test@example.com", "timestamp": "2026-01-29T10:30:00", "status": "approved", "queries_granted": 10, "approved_at": "2026-01-29T10:45:00", "request_id": "abc12345_1738155000"}
```

### `logs/approved_extensions.json`
```json
{
  "abc12345": {
    "queries_granted": 10,
    "approved_at": "2026-01-29T10:45:00",
    "request_id": "abc12345_1738155000",
    "email": "test@example.com"
  }
}
```

## Environment Variables

### Required for Extension Requests
```bash
ADMIN_EMAIL=eric@example.com
APP_URL=https://your-app-domain.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password  # NOT regular password!
```

### Existing (Still Required)
```bash
OPENAI_API_KEY=sk-...
FLASK_SECRET_KEY=<64-char-hex>
ADMIN_RESET_KEY=<32-char-hex>
```

## SMTP Configuration Notes

### Gmail Setup
1. Enable 2-Factor Authentication on Google Account
2. Generate App Password: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Use app password (not regular password) in `SMTP_PASSWORD`

### Alternative Providers
- **SendGrid**: More reliable for production, use API instead of SMTP
- **Mailgun**: Similar to SendGrid
- **Amazon SES**: Good for AWS deployments

## Security Considerations

1. **Rate Limiting**
   - One request per session via `has_pending_request()`
   - Could add IP-based rate limiting

2. **Email Validation**
   - Strict regex prevents false positives
   - Consider checking for disposable email domains

3. **Admin Authentication**
   - Reuses existing `ADMIN_RESET_KEY` pattern
   - All admin endpoints require key validation

4. **Session Hijacking Prevention**
   - Extensions tied to server-side session ID
   - Cannot be manipulated by client

## Testing Checklist

- [ ] Email detection works (valid formats accepted, invalid rejected)
- [ ] Extension request creates NDJSON entry
- [ ] Email notification sent to admin
- [ ] Admin UI shows pending request
- [ ] Approve button grants queries
- [ ] Session resumes with increased limit
- [ ] Query count updates correctly (e.g., 20/30)
- [ ] Duplicate request prevention works
- [ ] Deny button marks request as denied
- [ ] Filter tabs work (Pending/Approved/Denied/All)

## Deployment Steps

1. **Update Environment Variables**
   - Add all new SMTP and admin email variables to `.env` or Dokploy UI

2. **Test SMTP Configuration**
   ```bash
   python3 -c "
   import smtplib
   from email.message import EmailMessage
   msg = EmailMessage()
   msg['Subject'] = 'Test'
   msg['From'] = 'your@email.com'
   msg['To'] = 'your@email.com'
   msg.set_content('Test')
   with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
       smtp.starttls()
       smtp.login('your@email.com', 'app-password')
       smtp.send_message(msg)
   "
   ```

3. **Rebuild Docker Image**
   ```bash
   docker build -t profile-gpt .
   ```

4. **Deploy to Dokploy**
   - Push changes to repository
   - Dokploy will rebuild automatically
   - Verify all environment variables are set

5. **Verify Logs Directory**
   - Ensure `/data/logs` is writable
   - Check `extension_requests.ndjson` and `approved_extensions.json` are created

## Future Enhancements (Out of Scope)

- Email notification to user when approved/denied
- Configurable query grant amounts (dropdown: 5, 10, 20)
- Analytics dashboard (approval rates, average grants)
- Auto-approve for trusted email domains
- Time-based expiration on approved extensions
- Integration with email service APIs (SendGrid, Mailgun)

## Rollback Plan

If issues arise, revert to version 0.9.1:
```bash
git checkout <previous-commit-hash>
docker build -t profile-gpt .
```

Extension request feature is fully optional - app works normally without SMTP configuration (requests logged but no emails sent).

## Known Limitations

1. **Email Sending Failures**
   - If SMTP fails, request is still logged but admin won't receive notification
   - Consider monitoring `extension_requests.ndjson` manually

2. **Session Persistence**
   - Approved extensions stored in file-based JSON
   - For high traffic, consider migrating to database

3. **Email Detection**
   - Simple regex may miss some edge cases
   - Multiple emails in one message: only first is extracted

## Success Metrics

- Extension request creation success rate
- Email notification delivery rate
- Admin approval/denial response time
- User satisfaction with extended sessions
