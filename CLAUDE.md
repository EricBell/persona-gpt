# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ProfileGPT is an AI-powered "Ask Eric" web app for recruiters. It uses OpenAI's Responses API to simulate Eric Bell's personality and experience when answering questions.

## Tech Stack

- Python Flask web framework
- Gunicorn WSGI server
- OpenAI Responses API
- uv package manager
- Docker (slim Python image)

## Configuration

- API credentials: `.env` file (gitignored)
- AI persona/system instructions: stored in a local file accessible to the Flask app

## Running the App

```bash
# Local development
uv venv
uv pip install -e .
uv run python app.py --mode=local

# Docker
docker build -t profile-gpt .
docker run -p 5000:5000 --env-file .env \
  -v $(pwd)/persona.txt:/data/persona.txt \
  -v $(pwd)/logs:/data/logs \
  profile-gpt

# Docker Compose
docker-compose up -d
```

## Version Management

Version format: MAJOR.MINOR.PATCH (starting at 0.1.0)

**Incrementing rules:**
- MINOR: Increment when completing a new feature set
- PATCH: Increment when fixing a bug or set of bugs in one turn
- MAJOR: Only increment when instructed by the user (resets MINOR and PATCH to 0)

Update both `version.py` and `pyproject.toml` when changing versions.

## Copyright Notice Requirements

**All new files should include a copyright notice when applicable:**

1. **Format**: `Copyright Polymorph Corporation (YYYY)` where YYYY is the current year (e.g., 2026)

2. **File Types & Placement**:
   - **Code files** (.py, .js, .css, etc.): Add as comment at top of file
   - **Config files** (.yml, .toml, .json, etc.): Add as comment if format supports it
   - **Documentation** (.md): Optional - may be omitted for pure documentation files

3. **Comment Style**: Always use appropriate comment syntax for the file type:
   ```python
   # Copyright Polymorph Corporation (2026)
   ```
   ```yaml
   # Copyright Polymorph Corporation (2026)
   ```

4. **Updating Existing Files**: If a copyright notice already exists, update the year to current year if not already included

## Deployment Checklist

**When adding new Python modules or features, ALWAYS update these files:**

1. **`Dockerfile`** - Add new `.py` modules to the COPY commands (around line 25-33)
2. **`version.py`** and **`pyproject.toml`** - Increment version per rules above
3. **`app.py`** - Add imports and route handlers as needed
4. **`templates/`** - Add any new HTML templates
5. **`static/`** - Add any new CSS/JS files

**Docker deployment uses explicit file listing** - if you create a new Python module and don't add it to the Dockerfile, it won't be included in the Docker image and the app will fail to start.

## Dokploy Deployment

This app is ready for deployment on Dokploy (self-hosted PaaS).

**Option 1: Docker Compose (Recommended)**
1. In Dokploy, create a new "Compose" application
2. Point to this repository
3. Set environment variables in Dokploy UI:
   - `OPENAI_API_KEY` (required)
   - `FLASK_SECRET_KEY` (required - MUST be 32+ characters, generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
   - `ADMIN_RESET_KEY` (optional - if set, should be 16+ characters for security)
4. Configure volumes for persistent data (`persona.txt`, `logs/`)

**CRITICAL:** The application will refuse to start if `FLASK_SECRET_KEY` is not set or uses a weak/known value. Never use example values from documentation in production.

**Option 2: Dockerfile**
1. Create a new "Docker" application
2. Point to this repository (uses Dockerfile)
3. Set environment variables in Dokploy UI (same requirements as above)
4. Add volume mounts:
   - `./persona.txt:/data/persona.txt:ro`
   - `./logs:/data/logs`

**Health Check:** The app exposes `/health` endpoint for container monitoring.

## Query Limit Extension Requests

The app includes a system for users to request additional queries when they hit the session limit:

1. **User Flow:**
   - User hits query limit (20/20 by default)
   - System prompts: "To request more questions, send a message with your email address"
   - User types email in chat
   - System detects email, creates extension request, sends notification to admin
   - User receives confirmation message

2. **Admin Workflow:**
   - Eric receives email notification when extension request is created
   - Admin visits `/extension-requests?key=YOUR_KEY` to review pending requests
   - Admin approves/denies requests and specifies number of queries to grant (default: 10)
   - Approved sessions automatically get increased query limits

3. **Required Environment Variables:**
   ```bash
   ADMIN_EMAIL=eric@example.com
   APP_URL=https://your-app-domain.com
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USE_TLS=true
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=your-app-password
   ```

4. **Key Files:**
   - `email_detector.py` - Email extraction/validation
   - `extension_manager.py` - Request management (CRUD)
   - `email_notifier.py` - SMTP email notifications
   - `templates/extension_requests.html` - Admin UI
   - `logs/extension_requests.ndjson` - Request log
   - `logs/approved_extensions.json` - Session approval tracking

## Guiding Document

**See [Intentions.md](Intentions.md)** - This file defines the core principles that guide all development decisions for this project. The AI persona, response style, and interaction patterns described there should inform every feature and implementation choice.
