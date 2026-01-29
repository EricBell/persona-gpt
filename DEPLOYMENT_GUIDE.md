# Query Limit Extension Request System - Deployment Guide

## Quick Start

This guide walks you through deploying the query limit extension request feature to production.

## Prerequisites

1. SMTP email account (Gmail, SendGrid, Mailgun, etc.)
2. Admin email address to receive notifications
3. Dokploy or Docker environment

## Step 1: Configure SMTP (Gmail Example)

### Gmail Setup
1. **Enable 2-Step Verification** (required for App Passwords):
   - Go to [myaccount.google.com/security](https://myaccount.google.com/security)
   - Under "How you sign in to Google", click **2-Step Verification**
   - Follow the setup process if not already enabled

2. **Create App Password**:
   - Go directly to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Or search for "App Passwords" in your Google Account settings
   - Select app: **Mail**
   - Select device: **Other (Custom name)** → Enter "PersonaGPT"
   - Click **Generate**
   - Copy the 16-character password (shown in yellow box)
   - **Important**: Save this password - you won't be able to see it again

### Test SMTP Connection
```bash
python3 -c "
import smtplib
from email.message import EmailMessage

msg = EmailMessage()
msg['Subject'] = 'PersonaGPT Test'
msg['From'] = 'your-email@gmail.com'
msg['To'] = 'your-email@gmail.com'
msg.set_content('Test email from PersonaGPT')

with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
    smtp.starttls()
    smtp.login('your-email@gmail.com', 'your-app-password-here')
    smtp.send_message(msg)
    print('Email sent successfully!')
"
```

## Step 2: Set Environment Variables

### Required Variables
```bash
# Admin Configuration
ADMIN_EMAIL=eric@polymorph.co
APP_URL=https://profile-gpt.your-domain.com

# SMTP Configuration (Gmail)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password

# Existing Variables (Still Required)
OPENAI_API_KEY=sk-...
FLASK_SECRET_KEY=<64-char-hex>
ADMIN_RESET_KEY=<32-char-hex>
```

### Alternative SMTP Providers

#### SendGrid
```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=apikey
SMTP_PASSWORD=your-sendgrid-api-key
```

#### Mailgun
```bash
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=postmaster@your-domain.mailgun.org
SMTP_PASSWORD=your-mailgun-password
```

#### AWS SES
```bash
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-smtp-username
SMTP_PASSWORD=your-smtp-password
```

## Step 3: Deploy to Dokploy

### Option A: Docker Compose (Recommended)

1. **Update Environment Variables in Dokploy UI:**
   - Navigate to your PersonaGPT application
   - Go to **Settings** → **Environment Variables**
   - Add all required SMTP variables listed above

2. **Verify Volumes:**
   - Ensure `./persona.txt:/data/persona.txt` is mounted
   - Ensure `./logs:/data/logs` is mounted (must be writable)

3. **Rebuild and Deploy:**
   - Dokploy will automatically rebuild on git push
   - Or manually trigger rebuild in Dokploy UI

### Option B: Manual Docker Deployment

```bash
# Build image
docker build -t profile-gpt:0.10.0 .

# Run container
docker run -d \
  --name profile-gpt \
  -p 5000:5000 \
  --env-file .env \
  -v $(pwd)/persona.txt:/data/persona.txt:ro \
  -v $(pwd)/logs:/data/logs \
  profile-gpt:0.10.0
```

## Step 4: Verify Deployment

### 1. Check Health Endpoint
```bash
curl https://your-app-domain.com/health
# Expected: {"status":"healthy","version":"0.10.0"}
```

### 2. Test Extension Request Flow

1. Open app in browser
2. Use all 20 queries to hit limit
3. Submit email in chat: `test@example.com`
4. Verify you see: "Extension request received! We'll review your request..."

### 3. Check Admin Email
- Email should arrive at `ADMIN_EMAIL` with subject: "PersonaGPT Extension Request from test@example.com"
- Email contains link to admin UI

### 4. Access Admin UI
- Visit: `https://your-app-domain.com/extension-requests?key=YOUR_KEY`
- Should see pending request in table
- Click "Approve", grant queries (e.g., 10)

### 5. Verify Session Extension
- Return to original browser session
- Submit a message
- Query count should show: "20/30" (or updated limit)
- Message should go through

## Step 5: Monitor Logs

### Check Extension Request Log
```bash
# Docker
docker exec profile-gpt cat /data/logs/extension_requests.ndjson

# Dokploy
# View via Dokploy file browser or SSH
cat /path/to/logs/extension_requests.ndjson
```

### Check Approved Extensions
```bash
# Docker
docker exec profile-gpt cat /data/logs/approved_extensions.json

# Dokploy
cat /path/to/logs/approved_extensions.json
```

### Check Application Logs
```bash
# Docker
docker logs profile-gpt

# Dokploy
# View in Dokploy UI → Logs tab
```

## Troubleshooting

### Email Notifications Not Sending

1. **Check SMTP credentials:**
   ```bash
   # Verify environment variables are set
   docker exec profile-gpt env | grep SMTP
   ```

2. **Test SMTP connection:**
   ```bash
   docker exec profile-gpt python3 -c "
   import smtplib
   smtp = smtplib.SMTP('smtp.gmail.com', 587)
   smtp.starttls()
   smtp.login('user', 'pass')
   print('Connected!')
   "
   ```

3. **Check application logs for errors:**
   ```bash
   docker logs profile-gpt | grep -i "email\|smtp"
   ```

### Extension Requests Not Creating

1. **Verify logs directory is writable:**
   ```bash
   docker exec profile-gpt ls -la /data/logs/
   ```

2. **Check email detection:**
   ```bash
   docker exec profile-gpt python3 -c "
   from email_detector import extract_email
   print(extract_email('test@example.com'))
   "
   ```

### Admin UI Not Accessible

1. **Verify ADMIN_RESET_KEY is set:**
   ```bash
   docker exec profile-gpt env | grep ADMIN_RESET_KEY
   ```

2. **Check route registration:**
   ```bash
   docker exec profile-gpt python3 -c "
   from app import app
   print([r.rule for r in app.url_map.iter_rules()])
   " | grep extension
   ```

### Session Extensions Not Applying

1. **Check approved_extensions.json exists:**
   ```bash
   docker exec profile-gpt cat /data/logs/approved_extensions.json
   ```

2. **Verify session ID matches:**
   - Open browser console
   - Check session cookie or session storage
   - Compare with `session_id` in `approved_extensions.json`

## Security Checklist

- [ ] SMTP credentials stored in environment variables (not committed to git)
- [ ] ADMIN_RESET_KEY is strong (16+ characters)
- [ ] FLASK_SECRET_KEY is unique (32+ characters)
- [ ] ADMIN_EMAIL is correct and monitored
- [ ] APP_URL is HTTPS (not HTTP) in production
- [ ] `/extension-requests` endpoint requires authentication
- [ ] Logs directory permissions are secure

## Rollback Procedure

If issues arise, revert to previous version:

```bash
# Checkout previous commit
git checkout d5b4381  # or whatever commit before extension feature

# Rebuild Docker image
docker build -t profile-gpt:0.9.1 .

# Redeploy
# (Use Dokploy UI or docker run command)
```

Note: Extension request feature is gracefully degradable - if SMTP fails, requests are still logged but admin won't receive emails.

## Next Steps

1. **Monitor extension requests** via `/extension-requests` admin UI
2. **Adjust query grant amounts** based on user needs (default: 10)
3. **Review approval patterns** to identify trusted domains for potential auto-approval
4. **Consider analytics** to track extension request trends

## Support

For issues or questions:
- Check `IMPLEMENTATION_SUMMARY.md` for technical details
- Review application logs for error messages
- Verify environment variables are correctly set
- Test SMTP connection independently

---

**Version:** 0.10.0
**Last Updated:** 2026-01-29
