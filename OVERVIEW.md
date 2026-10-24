# ProfileGPT ("Ask Eric") — Overview

> A Flask web app that lets recruiters chat with an LLM persona of Eric Bell, plus a job-description vetting tool and admin dashboards for usage, logs, and session-reset requests.

## Purpose

Recruiters get an interactive way to ask preliminary questions about Eric's experience and working style. The persona comes from a text file (`persona.txt`) used as the system prompt. Guardrails keep usage on-topic and cheap: an LLM intent classifier filters off-topic questions before the main call, and per-session limits cap total and off-topic queries. Design principles are in `Intentions.md`: respectful, concise, optimistic, and honest about unknowns. Current version is 0.16.1 (`version.py`, `pyproject.toml`).

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+ (Docker image uses 3.12-slim), Flask 3 |
| Server | Gunicorn (2 workers, 4 threads) |
| AI | OpenAI `gpt-4o-mini` through `client.chat.completions.create` |
| Packaging | uv, `pyproject.toml` |
| Frontend | Jinja templates, `static/js/main.js`, `static/css/style.css` |
| Deploy | Docker / docker-compose on Dokploy, Traefik label |
| Tests | None found |

## Directory Structure

```
app.py               Flask app: all routes, session/limit logic, config loading (~1060 lines)
intent_classifier.py LLM classifier prompt, refusal/warning text, company-name extraction from persona
intent_validator.py  (not imported anywhere, not in Dockerfile)
job_vetting.py       /vet logic: sanitize and evaluate a job description against the persona
messages.py          HELP_RESPONSE and META_QUESTIONS (answered without calling OpenAI)
query_logger.py      Writes chat interactions to daily NDJSON logs
usage_tracker.py     Token/cost tracking (NDJSON), stats, OpenAI Usage API fetch and comparison
dataset_manager.py   Parses and filters query logs for the /dataset view
extension_manager.py Reset-request CRUD (logs/extension_requests.ndjson, approved_resets.json)
email_detector.py    Extracts an email address from a chat message
email_notifier.py    SMTP notification to admin on reset requests
config_validator.py  Startup validation of FLASK_SECRET_KEY / ADMIN_RESET_KEY
analyze_logs.py      Offline log analysis script
templates/           index, error, dataset, extension_requests, usage_stats, usage_api
static/              css/style.css, js/main.js
persona.txt(.example) System prompt (the real one is mounted at runtime)
config.json / config.example.json  Hot-tunable settings
mockups/             Static HTML design explorations (not used by the app)
*.md                 CLAUDE.md, Intentions.md, PRD.md, README, DEPLOYMENT_GUIDE, USAGE_*.md, etc.
```

## Architecture

**Chat flow (`POST /chat`, `app.py:294`):**
1. Apply any admin-approved session reset (`check_and_apply_reset`).
2. If the session hit its total limit (default 50) or the off-topic cutoff (10), return 429. A message containing an email address creates a reset request instead (`extension_manager`) and emails the admin. A session can request a reset only once.
3. Sanitize the message and enforce `MAX_QUERY_LENGTH`.
4. If the message is a meta/help question, return the hardcoded `HELP_RESPONSE` with no API call and no counter change.
5. Classify the intent with `gpt-4o-mini` (`max_tokens=10`, temperature 0). If the result is `OUT_OF_SCOPE`, increment the off-topic count and return a canned refusal. From 5 off-topic questions on, the warning text is used instead. If classification errors or is ambiguous, the message is treated as `IN_SCOPE`.
6. For in-scope messages, load `persona.txt` (re-read on every request) and send it as the system message, followed by the conversation history. The call uses `gpt-4o-mini` with `max_tokens=500` and temperature 0.7.
7. Log token usage (`usage_tracker`) and the interaction (`query_logger`) and return JSON with counters.

**State:** Conversation history and counters (`in_scope_count`, `out_of_scope_count`, `total_turns`) live in the signed Flask cookie session. There is no server-side session store or database. History is trimmed to `conversation_history_limit`, which is re-read from `config.json` on each request and falls back to the `CONVERSATION_HISTORY_LIMIT` env var.

**Other routes:**
- `/` is the UI.
- `/health` is the container health check.
- `/vet` POST evaluates a job description.
- `/status` and `/reset` are session helpers.
- `/dataset` is the log viewer.
- `/extension-requests`, `/approve-extension` and `/deny-extension` handle reset requests.
- `/usage-stats` shows local usage.
- `/usage-api` compares local usage with OpenAI's Usage API.
- The admin routes are protected by a `?key=` query param checked against `ADMIN_RESET_KEY`.
- 404 and 500 render `templates/error.html`.

## Integrations

- **OpenAI** (`openai` SDK): chat, classification, and job vetting, all on `gpt-4o-mini`. `OPENAI_ADMIN_API_KEY` is used only by `/usage-api` (`usage_tracker.fetch_openai_usage`, via `httpx`).
- **SMTP** (Gmail by default): reset-request notifications to the admin (`email_notifier.py`).
- No auth provider, analytics, or payment services.

## Database & Data Layer

There is no database. Everything is flat files under `QUERY_LOG_PATH` (`./logs`, or `/data/logs` in Docker):
- Daily query logs (NDJSON), written by `query_logger.py`.
- `usage_tracking.ndjson`.
- `extension_requests.ndjson`.
- `approved_resets.json`.

## Connectivity & Configuration

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required. Project key for chat and classification |
| `OPENAI_ADMIN_API_KEY` | Optional. Admin key for the Usage API comparison |
| `FLASK_SECRET_KEY` | Required, 32+ characters. The app refuses to start with a weak or known value |
| `ADMIN_RESET_KEY` | Optional, 16+ characters. Gates the admin pages |
| `MAX_QUERIES_PER_SESSION` | Total question cap (code default 50) |
| `OUT_OF_SCOPE_WARNING_THRESHOLD` / `OUT_OF_SCOPE_CUTOFF_THRESHOLD` | Off-topic warning and cutoff (5 / 10) |
| `MAX_QUERY_LENGTH` / `MAX_JOB_DESCRIPTION_LENGTH` | Input caps (500 / 5000) |
| `CONVERSATION_HISTORY_LIMIT` | History fallback (20) |
| `PERSONA_FILE_PATH`, `CONFIG_FILE_PATH`, `QUERY_LOG_PATH` | File locations (`/data/...` in Docker) |
| `ADMIN_EMAIL`, `APP_URL`, `SMTP_*` | Reset-request email |
| `PORT` | Defaults to 5000 |

Docker mounts `../files/persona.txt` to `/data/persona.txt` and `../files/logs` to `/data/logs`. The `config.json` mount is optional and commented out in `docker-compose.yml`. The image bakes in `config.example.json` as the default.

## Key Entry Points

- `app.py` — bootstrap (secret validation, env parsing), then `chat()`.
- `intent_classifier.py` — the classification prompt.
- `usage_tracker.py` — the largest helper module.
- `CLAUDE.md` and `Intentions.md` — project rules and persona intent.
- Run locally with `uv run python app.py --mode=local`.

## Notes & Gotchas

- **Explicit Dockerfile COPY list.** Any new `.py` module must be added to the Dockerfile or the container will fail at import. `intent_validator.py` is currently absent from the Dockerfile and unused, which is harmless unless it gets imported.
- **Docs and code disagree on defaults.** `CLAUDE.md` says the Responses API, but the code uses Chat Completions. The Dockerfile `ENV` sets `MAX_QUERIES_PER_SESSION=20` and `docker-compose.yml` defaults it to 20, while the code and docs default to 50. The Dockerfile also sets `FLASK_ENV=development`.
- **Session state is client-side.** Cookies are signed but not encrypted, and clearing cookies resets a user's limits. Reset approvals are matched by session ID.
- **Classifier fails open.** Errors send the message to the full conversation call.
- **Housekeeping rules:** bump `version.py` and `pyproject.toml` together, add `Copyright Polymorph Corporation (2026)` to new files, and never run git commits (the user commits).
