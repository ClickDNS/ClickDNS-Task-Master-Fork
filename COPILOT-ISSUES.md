# Task-Master — Full Issue Backlog for GitHub Copilot

> **Generated:** 2026-03-07  
> **Total open issues:** 83 (74 Todo, 8 Backlog, 1 In Review)  
> **Purpose:** Complete issue list with Copilot-optimised fix hints, grouped by category. Follow the migration steps before and after implementing changes.

---

## Table of Contents

1. [Pre-Migration Checklist](#pre-migration-checklist)
2. [New .env Variables Required](#new-env-variables-required)
3. [CRITICAL — Authentication & Access Control](#critical--authentication--access-control)
4. [CRITICAL — Secrets & Git History](#critical--secrets--git-history)
5. [HIGH — HTTP Security Headers & CSP](#high--http-security-headers--csp)
6. [HIGH — CSRF Protection](#high--csrf-protection)
7. [HIGH — Input Validation & Error Handling](#high--input-validation--error-handling)
8. [HIGH — Session Security](#high--session-security)
9. [HIGH — Dependencies & CVEs](#high--dependencies--cves)
10. [HIGH — Rate Limiting](#high--rate-limiting)
11. [MEDIUM — Firebase / Database Safety](#medium--firebase--database-safety)
12. [MEDIUM — IP Whitelist & Proxy Trust](#medium--ip-whitelist--proxy-trust)
13. [MEDIUM — Timing Attack Vectors](#medium--timing-attack-vectors)
14. [MEDIUM — CORS Configuration](#medium--cors-configuration)
15. [MEDIUM — Code Duplication & Refactoring](#medium--code-duplication--refactoring)
16. [MEDIUM — Discord Bot Correctness](#medium--discord-bot-correctness)
17. [MEDIUM — Datetime / Timezone Correctness](#medium--datetime--timezone-correctness)
18. [LOW — Error Handling & Silent Failures](#low--error-handling--silent-failures)
19. [LOW — Code Quality & Dead Code](#low--code-quality--dead-code)
20. [LOW — Logging & Observability](#low--logging--observability)
21. [LOW — Configuration Hygiene](#low--configuration-hygiene)
22. [POST-Migration Verification Checklist](#post-migration-verification-checklist)

---

## Pre-Migration Checklist

**Complete these steps BEFORE making any code changes. Order matters.**

### Step 1 — Rotate all compromised secrets (do this first, right now)

The following secrets are in git history and must be rotated **before** any fix is deployed. Even after removing from code, the git history retains the old values.

```bash
# 1. Rotate Firebase service account credentials
#    → Go to Google Cloud Console → IAM → Service Accounts → Delete old key → Create new key
#    → Download new credentials.json (do NOT commit it — store it securely)

# 2. Rotate Flask SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"
#    → Copy output → put in web_app/.env as SECRET_KEY=<value>

# 3. Rotate CARBON_API_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"
#    → Update in web_app/.env and anywhere the Carbon API uses it

# 4. Rotate TASKMASTER_API_KEY if exposed
#    → Generate new token, update in both web_app/.env and koda-tools config

# 5. Rotate DISCORD_BOT_TOKEN
#    → Discord Developer Portal → Regenerate bot token → update discord_bot/.env
```

### Step 2 — Git history purge for credentials.json (CLI-132, CLI-373, CLI-272)

```bash
# WARNING: This rewrites git history. Coordinate with George before running.
# All collaborators must re-clone after this.

cd ~/projects/ClickDNS-Task-Master

# Install git-filter-repo (preferred over BFG)
pip install git-filter-repo

# Purge credentials.json and any committed .env files from ALL history
git filter-repo --invert-paths \
  --path credentials.json \
  --path web_app/.env \
  --path .env \
  --force

# Force-push to origin (requires bypassing branch protection)
git push origin main --force-with-lease

# Invalidate GitHub's cached views of the old commits
# → Go to GitHub → Settings → Danger Zone → contact support if needed
# → All collaborators MUST: git clone <repo> (fresh clone, not git pull)
```

### Step 3 — Move credentials.json out of the repo

```bash
# Move to a secure location outside the repo
cp credentials.json ~/.secrets/task-master-firebase-credentials.json
chmod 600 ~/.secrets/task-master-firebase-credentials.json

# Add to .env
echo 'FIREBASE_CREDENTIALS_PATH=/path/to/.secrets/task-master-firebase-credentials.json' >> web_app/.env

# Update .gitignore (root level)
echo 'credentials.json' >> .gitignore
echo '*.json' >> .gitignore  # or be specific
echo '.env' >> .gitignore
```

### Step 4 — Create the new .env files from the template below before deploying

See [New .env Variables Required](#new-env-variables-required).

### Step 5 — Install new Python dependencies (after requirements.txt changes)

```bash
cd ~/projects/ClickDNS-Task-Master/web_app
source ../venv/bin/activate
pip install -r requirements.txt
# Then restart the service:
systemctl --user restart task-master-web
```

---

## New .env Variables Required

Add these to `web_app/.env`. Values marked `CHANGE_ME` must be set — the app will refuse to start with placeholder values after the hardened startup check is added.

```dotenv
# ── Authentication ────────────────────────────────────────────────────────────
# Strong random secret key (min 32 bytes hex). Generate: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=CHANGE_ME

# App password for web login (replaces zero-auth system)
# Generate: python3 -c "import secrets; print(secrets.token_urlsafe(24))"
APP_PASSWORD=CHANGE_ME

# Single-user mode username (if set, login is auto-bypassed for this user — keep for internal use)
TASKMASTER_USERNAME=george

# ── Firebase ─────────────────────────────────────────────────────────────────
# Path to Firebase credentials JSON (outside the repo)
FIREBASE_CREDENTIALS_PATH=/home/george/.secrets/task-master-firebase-credentials.json
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com

# ── API Keys ─────────────────────────────────────────────────────────────────
# Carbon API key for inter-service auth (generate fresh)
CARBON_API_KEY=CHANGE_ME

# Task-Master public API key (used by koda-tools CLI)
TASKMASTER_API_KEY=CHANGE_ME

# ── koda-paste ───────────────────────────────────────────────────────────────
KODA_PASTE_URL=http://100.123.59.91:8845
KODA_PASTE_THRESHOLD=500
# Optional Tailscale proxy for koda-paste (userspace-networking mode)
# KODA_PASTE_PROXY=socks5://localhost:1055

# ── Session ───────────────────────────────────────────────────────────────────
# Remove SESSION_TYPE=filesystem (Flask-Session not installed — dead config)
# SESSION_TYPE=filesystem  ← DELETE THIS LINE

# ── Rate Limiting ─────────────────────────────────────────────────────────────
# Max login attempts per minute per IP
LOGIN_RATE_LIMIT=5
# Max API requests per minute per IP/token
API_RATE_LIMIT=60

# ── CORS ─────────────────────────────────────────────────────────────────────
# Comma-separated allowed origins for CORS
CORS_ORIGINS=https://task-master.clickdns.com.au,https://carbon.clickdns.com.au

# ── Proxy Trust ───────────────────────────────────────────────────────────────
# Number of trusted proxy hops (1 = Cloudflare Tunnel is the only proxy)
TRUSTED_PROXY_COUNT=1

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
```

Add these to `discord_bot/.env`:

```dotenv
# Discord bot token (regenerated after history purge)
DISCORD_BOT_TOKEN=CHANGE_ME

# koda-paste URL (must use HTTP port 8845 for bot — not 8844)
KODA_PASTE_URL=http://100.123.59.91:8845

# Firebase credentials (path or inline JSON)
FIREBASE_CREDENTIALS_PATH=/home/george/.secrets/task-master-firebase-credentials.json
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com

# Reminder channel Discord channel ID
REMINDER_CHANNEL=<discord_channel_id>

# Discord guild/forum IDs
TASKMASTER_GUILD_ID=<guild_id>
FORUM_CHANNEL_ID=<forum_channel_id>

# Single-user mode username
TASKMASTER_USERNAME=george
```

---

## CRITICAL — Authentication & Access Control

### CLI-57 / CLI-135 / CLI-197 — Web app login has zero authentication (any username accepted)

**File:** `web_app/app.py`  
**Priority:** URGENT  
**Severity:** CRITICAL

**Problem:** `login()` at line ~544 sets `session['username'] = username` for any non-empty string. There is no password check whatsoever.

```python
# CURRENT (broken — no auth):
if username:
    session['username'] = username
    return redirect(url_for('tasks'))
```

**Fix:** Add password-based authentication. Use `APP_PASSWORD` from `.env`. Use `secrets.compare_digest` to prevent timing attacks.

```python
import hashlib
import secrets

APP_PASSWORD = os.getenv('APP_PASSWORD', '')

def _check_password(candidate: str) -> bool:
    """Constant-time password check. Returns False if APP_PASSWORD not configured."""
    if not APP_PASSWORD:
        return False
    return secrets.compare_digest(
        hashlib.sha256(candidate.encode()).hexdigest(),
        hashlib.sha256(APP_PASSWORD.encode()).hexdigest()
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    if SINGLE_USER_MODE:
        session['username'] = SINGLE_USER_MODE
        return redirect(url_for('tasks'))
    if 'username' in session:
        return redirect(url_for('tasks'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if username and _check_password(password):
            session['username'] = username
            logger.info(f"User logged in: {username}")
            return redirect(url_for('tasks'))
        # Generic error — don't reveal which field is wrong
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')
```

Also update `web_app/templates/login.html` to add a password field:
```html
<input type="password" name="password" placeholder="Password" required>
```

**Startup guard** — add to app startup (prevents silent misconfiguration):
```python
if not os.getenv('APP_PASSWORD') and not SINGLE_USER_MODE:
    raise RuntimeError("APP_PASSWORD must be set in .env (or set TASKMASTER_USERNAME for single-user mode)")
if not os.getenv('SECRET_KEY') or os.getenv('SECRET_KEY') == 'dev-secret-key-change-in-production':
    raise RuntimeError("SECRET_KEY must be set to a strong random value in .env")
```

---

### CLI-58 — /refresh slash command not gated to admins/owners

**File:** `discord_bot/bot.py`  
**Priority:** HIGH

**Problem:** The `/refresh` command at line ~312 can be triggered by any Discord server member.

```python
# CURRENT (no permission check):
@bot.tree.command(name="refresh", description="Manually refresh forum threads and dashboard")
async def refresh_taskboard(interaction: discord.Interaction):
```

**Fix:** Check that the invoking user is a guild admin or has the `manage_guild` permission.

```python
@bot.tree.command(name="refresh", description="Manually refresh forum threads and dashboard")
async def refresh_taskboard(interaction: discord.Interaction):
    # Gate to admins/owners only
    if not interaction.user.guild_permissions.manage_guild and \
       interaction.user.id != interaction.guild.owner_id:
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.",
            ephemeral=True
        )
        return
    # ... rest of handler
```

---

## CRITICAL — Secrets & Git History

### CLI-132 / CLI-373 / CLI-272 — credentials.json and .env committed to git

**Files:** `credentials.json`, `web_app/.env`, `.env`, `.gitignore`  
**Priority:** URGENT

**Problem:** Firebase service account credentials (`credentials.json`) and live secrets (`.env`) are tracked by git and visible in commit history.

**Fix (code changes after history purge above):**

1. **Load Firebase credentials from env path, not hardcoded file:**

```python
# web_app/app.py — replace hardcoded credentials loading
import os
from firebase_admin import credentials as fb_credentials

_creds_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'credentials.json')
if os.path.exists(_creds_path):
    cred = fb_credentials.Certificate(_creds_path)
    firebase_admin.initialize_app(cred, {
        'databaseURL': os.getenv('FIREBASE_DATABASE_URL')
    })
else:
    logger.error(f"Firebase credentials not found at {_creds_path}")
```

2. **Root `.gitignore` — add missing patterns** (also fixes CLI-200, CLI-406, CLI-430):

```gitignore
# Secrets — root level
.env
.env.*
!.env.example
credentials.json
*.json
!requirements.json
!vercel.json
!railway.json
!config.ini

# Web app
web_app/.env
web_app/.env.*

# Discord bot
discord_bot/.env
discord_bot/.env.*
```

3. **Create `.env.example` files** as safe documentation templates (commit these, not real values).

---

### CLI-378 — 7 exposed secrets (Aikido scan)

**Priority:** HIGH

Rotate all secrets listed in Aikido. After rotation, ensure all secret values are loaded from environment variables only — never hardcoded or in committed files.

---

### CLI-386 — Tailscale auth key co-located with app runtime secrets

**File:** `web_app/.env`  
**Priority:** HIGH

Move `TS_AUTH_KEY` out of `web_app/.env` into a separate `tailscale.env` that is managed separately (used only at startup, not loaded by the Flask app). The Flask app should never have access to the Tailscale auth key.

---

## HIGH — HTTP Security Headers & CSP

### CLI-404 / CLI-440 — No HTTP security headers; CSP allows eval()

**File:** `web_app/app.py`  
**Priority:** HIGH / MEDIUM

**Problem:** No `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, or `Referrer-Policy` headers are set.

**Fix:** Add an `after_request` hook to inject all required security headers:

```python
import secrets as _secrets

@app.after_request
def set_security_headers(response):
    # Generate a per-request nonce for CSP
    nonce = _secrets.token_hex(16)
    response.headers['Content-Security-Policy'] = (
        f"default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        f"style-src 'self' 'unsafe-inline'; "   # tighten to nonce when templates are updated
        f"img-src 'self' data:; "
        f"connect-src 'self'; "
        f"frame-ancestors 'none'; "
        f"base-uri 'none'; "
        f"form-action 'self';"
        # Note: NO 'unsafe-eval' — this blocks eval(), setTimeout(string), etc.
    )
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    # Only set HSTS if behind HTTPS (Cloudflare Tunnel handles TLS termination)
    if request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response
```

---

### CLI-438 — Potential XSS via window.location.href (ClickDNS — separate repo)

**File:** `src/components/domain/TransferPendingCard.tsx` (in ClickDNS repo, not Task-Master)  
**Priority:** HIGH  
**Note:** This issue is in the ClickDNS frontend repo, not Task-Master. File here for awareness.

**Fix:** Validate redirect targets against an allowlist before assigning to `window.location.href`.

```typescript
const ALLOWED_REDIRECT_HOSTS = ['clickdns.com.au', 'dev.clickdns.com.au'];

function safePush(url: string) {
  try {
    const parsed = new URL(url, window.location.origin);
    if (!ALLOWED_REDIRECT_HOSTS.includes(parsed.hostname)) {
      console.error('Blocked redirect to untrusted host:', parsed.hostname);
      return;
    }
    window.location.href = parsed.href;
  } catch {
    console.error('Invalid redirect URL:', url);
  }
}
```

---

## HIGH — CSRF Protection

### CLI-140 / CLI-332 — No CSRF protection on any state-changing endpoint

**File:** `web_app/app.py`, `web_app/requirements.txt`  
**Priority:** HIGH

**Problem:** All `POST`, `PUT`, `DELETE` endpoints are vulnerable to Cross-Site Request Forgery. No CSRF tokens are validated.

**Fix:** Install `Flask-WTF` and enable CSRF globally, OR use the `flask-wtf` CSRF standalone protection.

```bash
# Add to web_app/requirements.txt:
Flask-WTF==1.2.2
```

```python
# web_app/app.py — add after app creation
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)

# For API endpoints that use Bearer token auth, exempt them from CSRF
# (they're protected by the token instead)
# Use @csrf.exempt on API-only routes that require Bearer tokens:

@app.route('/api/tasks', methods=['POST'])
@csrf.exempt          # API callers use Bearer token — CSRF token not applicable
@login_required
def create_task():
    ...

# For form-based routes (login, web UI), CSRF is enforced automatically.
# Add {% raw %}{{ csrf_token() }}{% endraw %} to all forms in templates:
```

In `web_app/templates/login.html`:
```html
<form method="POST">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <!-- ... rest of form ... -->
</form>
```

---

## HIGH — Input Validation & Error Handling

### CLI-334 / CLI-270 / CLI-202 — create_task / update_task crash if JSON body missing or malformed

**File:** `web_app/app.py` (functions `create_task`, `update_task`, and all API endpoints)  
**Priority:** HIGH

**Problem:** `request.get_json()` returns `None` if the request body is missing or `Content-Type` is wrong. Subsequent `data['name']` access crashes with `TypeError`/`KeyError` → 500.

**Fix:** Add a null-check and return 400 for all API endpoints that parse JSON bodies:

```python
def require_json():
    """Helper — returns parsed JSON body or raises 400."""
    data = request.get_json(silent=True)
    if data is None:
        from flask import abort
        abort(400, description="Request body must be valid JSON with Content-Type: application/json")
    return data

# In create_task():
@app.route('/api/tasks', methods=['POST'])
@login_required
def create_task():
    try:
        data = require_json()
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Task name is required'}), 400
        # ... rest of logic
    except Exception as e:
        logger.error(f"create_task error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
```

Apply the same pattern to `update_task`, `add_subtask`, `edit_subtask`, `toggle_subtask`.

---

### CLI-333 / CLI-260 — str(e) in API error responses leaks internal exception details

**File:** `web_app/app.py` — all `except` blocks that return `str(e)` to the client  
**Priority:** HIGH

**Problem:** All 10+ API error handlers do `return jsonify({'success': False, 'error': str(e)}), 500`. This exposes stack traces, file paths, and internal details to any caller.

**Fix:** Log the full exception server-side, return a generic message to the client:

```python
# WRONG (current):
except Exception as e:
    return jsonify({'success': False, 'error': str(e)}), 500

# CORRECT:
except Exception as e:
    logger.error(f"Unexpected error in {request.endpoint}: {e}", exc_info=True)
    return jsonify({'success': False, 'error': 'Internal server error'}), 500
```

Search for all occurrences:
```bash
grep -n "str(e)" web_app/app.py
```

Replace every instance where `str(e)` is sent in a JSON response. There are ~10 such lines.

---

### CLI-262 — No URL field validation (javascript: URLs accepted)

**File:** `web_app/app.py` — `create_task()` and `update_task()`  
**Priority:** MEDIUM

**Problem:** The `url` field on tasks is stored and returned without validation. A `javascript:alert(1)` URL is accepted and stored.

**Fix:** Validate URL scheme on input:

```python
from urllib.parse import urlparse

def validate_task_url(url: str) -> bool:
    """Return True if URL is safe to store (http/https only)."""
    if not url:
        return True  # empty is fine
    try:
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https')
    except Exception:
        return False

# In create_task and update_task, before saving:
task_url = data.get('url', '').strip()
if task_url and not validate_task_url(task_url):
    return jsonify({'success': False, 'error': 'URL must use http or https scheme'}), 400
```

---

### CLI-153 — No input length limits on API endpoints

**File:** `web_app/app.py`  
**Priority:** LOW

**Fix:** Add max length checks for all text inputs:

```python
MAX_TASK_NAME = 200
MAX_DESCRIPTION = 10000  # longer descriptions offloaded to koda-paste
MAX_URL = 2000
MAX_OWNER = 100

# In create_task / update_task, after JSON parsing:
if len(name) > MAX_TASK_NAME:
    return jsonify({'success': False, 'error': f'Task name must be ≤ {MAX_TASK_NAME} chars'}), 400
if description and len(description) > MAX_DESCRIPTION:
    return jsonify({'success': False, 'error': f'Description must be ≤ {MAX_DESCRIPTION} chars'}), 400
```

---

### CLI-269 — update_task returns HTTP 200 when task_id doesn't exist

**File:** `web_app/app.py` — `update_task()`  
**Priority:** MEDIUM

**Problem:** If a task with the given ID is not found, `update_task` silently returns 200 with `{"success": true}`.

**Fix:** Track whether a task was found and return 404 if not:

```python
def update_task(task_id):
    try:
        data = require_json()
        tasks = load_tasks(username)
        task_found = False
        for task in tasks:
            if task['id'] == task_id:
                task_found = True
                # ... update logic
                break
        if not task_found:
            return jsonify({'success': False, 'error': f'Task {task_id} not found'}), 404
        save_tasks(username, tasks)
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"update_task error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
```

---

## HIGH — Session Security

### CLI-137 / CLI-198 / CLI-403 / CLI-429 — Weak hardcoded fallback SECRET_KEY

**File:** `web_app/app.py` line 106  
**Priority:** HIGH

**Problem:**
```python
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
```
If `SECRET_KEY` is not set, a predictable fallback is used — attackers can forge session cookies.

**Fix:** Remove the fallback entirely. Fail loudly at startup if not configured:

```python
_secret_key = os.getenv('SECRET_KEY', '')
if not _secret_key:
    raise RuntimeError(
        "SECRET_KEY environment variable is required. "
        "Generate with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
    )
app.secret_key = _secret_key
```

---

### CLI-203 / CLI-405 — Session cookies missing Secure, HttpOnly, SameSite flags

**File:** `web_app/app.py`  
**Priority:** MEDIUM

**Fix:** Add after app creation:

```python
app.config.update(
    SESSION_COOKIE_SECURE=True,        # Only send over HTTPS
    SESSION_COOKIE_HTTPONLY=True,      # Not accessible from JavaScript
    SESSION_COOKIE_SAMESITE='Lax',     # CSRF mitigation
    SESSION_COOKIE_NAME='tmid',        # Non-default name (harder to enumerate)
    PERMANENT_SESSION_LIFETIME=3600,   # 1 hour expiry
)
```

---

### CLI-271 / CLI-417 — SESSION_TYPE=filesystem set but Flask-Session not installed

**File:** `web_app/app.py` line 107  
**Priority:** LOW / MEDIUM

**Problem:** `app.config['SESSION_TYPE'] = 'filesystem'` does nothing without `flask-session` installed. This is dead config that suggests server-side sessions are being used when they aren't.

**Fix:** Remove the dead config line (line 107), OR install and configure Flask-Session properly:

**Option A (simple — remove dead config):**
```python
# DELETE this line:
# app.config['SESSION_TYPE'] = 'filesystem'
```

**Option B (proper server-side sessions — recommended for production):**
```bash
# Add to requirements.txt:
Flask-Session==0.8.0
```
```python
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = '/tmp/task-master-sessions'
from flask_session import Session
Session(app)
```

---

## HIGH — Dependencies & CVEs

### CLI-439 — Upgrade Werkzeug (8 CVEs, 3 HIGH)

**File:** `web_app/requirements.txt`  
**Priority:** HIGH

```
# Change:
Werkzeug==3.0.1
# To:
Werkzeug==3.1.6
```

---

### CLI-377 — Major upgrade for gunicorn

**File:** `web_app/requirements.txt`  
**Priority:** HIGH

```
# Change:
gunicorn==21.2.0
# To:
gunicorn==23.0.0
# Note: Review gunicorn 23.x changelog for breaking changes before upgrading
```

---

### CLI-344 — Minor upgrade for aiohttp

**File:** `discord_bot/requirements.txt` (check for aiohttp there)  
**Priority:** URGENT

```bash
grep -r "aiohttp" */requirements.txt
# Upgrade to latest stable (check: https://github.com/aio-libs/aiohttp/releases)
```

---

### CLI-288 — Minor upgrade for h11

**File:** whichever requirements.txt contains h11  
**Priority:** URGENT

```bash
grep -r "h11" */requirements.txt
# Upgrade to latest stable (h11>=0.14.0)
```

---

### CLI-144 — Pin all dependencies to exact versions with known-good hashes

**File:** `web_app/requirements.txt`, `discord_bot/requirements.txt`  
**Priority:** MEDIUM

**Fix:** Generate a pinned `requirements.txt` with hashes:

```bash
cd web_app
pip install pip-tools
pip-compile --generate-hashes --output-file requirements.txt requirements.in
# Then use: pip install --require-hashes -r requirements.txt
```

---

### CLI-252 — requirements.txt missing core runtime dependencies

**File:** `web_app/requirements.txt`  
**Priority:** HIGH

**Problem:** `Flask`, `requests`, and `discord.py` are not listed in `requirements.txt` (they are implicit transitive deps but should be explicit for reproducibility).

**Fix:** Add explicit entries to `web_app/requirements.txt`:

```
Flask==3.1.0
requests==2.32.3
```

And to `discord_bot/requirements.txt` (create if missing):
```
discord.py==2.4.0
```

---

## HIGH — Rate Limiting

### CLI-337 — No rate limiting on any endpoint (login brute-force possible)

**File:** `web_app/app.py`, `web_app/requirements.txt`  
**Priority:** MEDIUM

**Fix:** Install `Flask-Limiter` and apply limits:

```bash
# Add to web_app/requirements.txt:
Flask-Limiter==3.9.0
```

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "60 per minute"],
    storage_uri="memory://",  # Switch to Redis for multi-process: "redis://localhost:6379"
)

# Apply stricter limit to login:
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    ...

# Apply to all API write endpoints:
@app.route('/api/tasks', methods=['POST'])
@limiter.limit("30 per minute")
@login_required
def create_task():
    ...
```

---

## MEDIUM — Firebase / Database Safety

### CLI-339 / CLI-263 / CLI-251 — Task ID = task name causes duplicate overwrite + path injection

**File:** `web_app/app.py` — `create_task()` around line 421  
**Priority:** MEDIUM

**Problem 1 (path injection):** Task names are used directly as Firebase keys. A task named `../../../admin` or similar could corrupt the Firebase data structure.

**Problem 2 (duplicate overwrite):** Two tasks with the same name silently overwrite each other because they share the same Firebase key.

```python
# CURRENT (broken):
task_id = task.get('id', task['name'])  # name used as ID!
tasks_data[task_id] = {...}
```

**Fix:** Always generate a UUID for new tasks. Never use the task name as the key:

```python
import uuid

# In create_task():
task_id = str(uuid.uuid4())  # Always generate a fresh UUID
new_task = {
    'id': task_id,
    'name': name,
    # ...
}
tasks_data[task_id] = new_task
```

For Firebase path safety, also validate that any incoming `task_id` path parameter only contains alphanumeric characters and hyphens:

```python
import re
_SAFE_TASK_ID = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')

def validate_task_id(task_id: str) -> bool:
    return bool(_SAFE_TASK_ID.match(task_id))

# In get_task, update_task, delete_task:
if not validate_task_id(task_id):
    return jsonify({'success': False, 'error': 'Invalid task ID'}), 400
```

---

### CLI-141 — Race condition: full task list read-modify-write

**File:** `web_app/app.py`  
**Priority:** MEDIUM

**Problem:** All writes use a pattern of load-entire-list → modify → save-entire-list. Concurrent requests (two users editing at the same time, or auto-refresh firing mid-edit) can cause one update to silently overwrite another.

**Fix (minimal):** Add a simple threading lock around load/modify/save cycles:

```python
import threading

_tasks_lock = threading.Lock()

# In create_task, update_task, delete_task, add_subtask, etc.:
with _tasks_lock:
    tasks = load_tasks(username)
    # ... modify ...
    save_tasks(username, tasks)
```

**Fix (proper, longer term):** Use Firebase atomic transactions or ETag-based conditional writes instead of full list reads. See Firebase `transaction()` docs.

---

## MEDIUM — IP Whitelist & Proxy Trust

### CLI-199 / CLI-250 / CLI-285 / CLI-335 — X-Forwarded-For trusted without ProxyFix

**File:** `web_app/app.py` — `check_ip_whitelist()` around line 259  
**Priority:** HIGH / MEDIUM

**Problem:** `request.headers.get('X-Forwarded-For', request.remote_addr)` is used directly. Any client can send a spoofed `X-Forwarded-For: 127.0.0.1` header to bypass IP whitelisting.

**Fix:** Use Werkzeug's `ProxyFix` middleware which correctly handles only the rightmost `N` hops from trusted proxies:

```python
from werkzeug.middleware.proxy_fix import ProxyFix

# After app creation:
# TRUSTED_PROXY_COUNT=1 means Cloudflare Tunnel is the single trusted proxy
_proxy_count = int(os.getenv('TRUSTED_PROXY_COUNT', '1'))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=_proxy_count, x_proto=_proxy_count)

# Now request.remote_addr will be the real client IP
# Remove manual X-Forwarded-For header parsing from check_ip_whitelist():
def check_ip_whitelist():
    client_ip = request.remote_addr  # ProxyFix has already resolved this
    # ... rest of whitelist check using client_ip
```

---

## MEDIUM — Timing Attack Vectors

### CLI-139 / CLI-201 / CLI-261 / CLI-336 — Non-constant-time API key comparison

**File:** `web_app/app.py` — `login_required()` and `ip_whitelist_check()` around lines 315–332  
**Priority:** HIGH / MEDIUM

**Problem:**
```python
# CURRENT (vulnerable to timing oracle):
if token == CARBON_API_KEY:
    ...
if auth_header[7:] == CARBON_API_KEY:
    ...
```

An attacker can measure response times to determine how many characters of the key are correct (timing oracle attack).

**Fix:** Use `secrets.compare_digest` for ALL API key comparisons:

```python
import secrets

# CORRECT:
if secrets.compare_digest(token.encode(), CARBON_API_KEY.encode()):
    ...
if secrets.compare_digest(auth_header[7:].encode(), CARBON_API_KEY.encode()):
    ...
```

Apply this fix everywhere `CARBON_API_KEY` or any other secret token is compared with `==`.

```bash
# Find all comparison sites:
grep -n "CARBON_API_KEY\|TASKMASTER_API_KEY" web_app/app.py | grep "=="
```

---

## MEDIUM — CORS Configuration

### CLI-338 — CORS_ORIGINS env var configured but Flask-CORS not installed

**File:** `web_app/app.py`, `web_app/requirements.txt`  
**Priority:** MEDIUM

**Problem:** `CORS_ORIGINS` is read from env but never applied because `flask-cors` is not installed and `CORS(app)` is never called.

**Fix:**

```bash
# Add to web_app/requirements.txt:
Flask-Cors==5.0.0
```

```python
from flask_cors import CORS

# After app creation:
_cors_origins = [o.strip() for o in os.getenv('CORS_ORIGINS', '').split(',') if o.strip()]
if _cors_origins:
    CORS(app, origins=_cors_origins, supports_credentials=True)
else:
    logger.warning("CORS_ORIGINS not configured — cross-origin API calls will fail")
```

---

## MEDIUM — Code Duplication & Refactoring

### CLI-142 — normalize_subtasks duplicated 4 times across codebase

**Files:** `web_app/app.py:190`, `discord_bot/database/task_model.py:11`, `Task-Master.py:91`  
**Priority:** MEDIUM

**Problem:** The same `normalize_subtasks()` function is copy-pasted in three different files. Bug fixes must be applied to all three.

**Fix:** Create a shared utility module:

```
task_master_shared/
├── __init__.py
└── subtasks.py      ← single canonical normalize_subtasks()
```

```python
# task_master_shared/subtasks.py
from typing import Any, Dict, List

def normalize_subtasks(subtasks: Any) -> List[Dict[str, Any]]:
    """Canonical normalize_subtasks — single source of truth."""
    if not subtasks:
        return []
    if isinstance(subtasks, dict):
        subtasks = list(subtasks.values())
    result = []
    used_ids = set()
    next_id = 1
    for st in subtasks:
        if not isinstance(st, dict):
            continue
        subtask_id = st.get('id')
        if isinstance(subtask_id, str) and subtask_id.isdigit():
            subtask_id = int(subtask_id)
        if not isinstance(subtask_id, int) or subtask_id <= 0 or subtask_id in used_ids:
            subtask_id = next_id
        used_ids.add(subtask_id)
        next_id = max(next_id, subtask_id + 1)
        result.append({
            'id': subtask_id,
            'title': str(st.get('title', '')),
            'completed': bool(st.get('completed', False)),
        })
    return result
```

Then replace all local copies with:
```python
from task_master_shared.subtasks import normalize_subtasks
```

---

### CLI-143 — Task class duplicated: Task-Master.py vs discord_bot/database/task_model.py

**Files:** `Task-Master.py` (desktop), `discord_bot/database/task_model.py`  
**Priority:** MEDIUM

**Problem:** Two separate `Task` class definitions that can diverge. Already has diverged — the desktop version has different fields.

**Fix (long-term):** Move the canonical `Task` model to `task_master_shared/task_model.py` and import from both locations. This is a larger refactor; file as a sprint item and do after CLI-142 (shared module is a prerequisite).

---

### CLI-61 / CLI-64 — ForumSyncService re-instantiated on every interaction

**File:** `discord_bot/bot.py`, `discord_bot/discord_ui/buttons.py`, `discord_bot/discord_ui/modals.py`  
**Priority:** MEDIUM / LOW

**Problem:** `ForumSyncService()` is instantiated inside button handlers and modal callbacks. This creates a new service object per interaction, which is wasteful and can introduce race conditions.

**Fix:** Create a single shared `forum_sync_service` instance at bot startup and pass it to handlers via a module-level singleton or the bot's app state:

```python
# discord_bot/bot.py — at module level
from services.forum_sync_service import ForumSyncService

_forum_sync = ForumSyncService()

@bot.event
async def on_ready():
    _forum_sync.set_bot(bot)
    _forum_sync.set_database(db_manager)
    # ...

# Export for use by buttons/modals:
def get_forum_sync() -> ForumSyncService:
    return _forum_sync
```

In `buttons.py` and `modals.py`:
```python
from bot import get_forum_sync

async def button_callback(interaction):
    forum_sync = get_forum_sync()  # shared instance, not a new one
    await forum_sync.sync_task(...)
```

---

### CLI-62 — _trigger_forum_sync() is a dead no-op stub in TaskService

**File:** `discord_bot/services/task_service.py`  
**Priority:** LOW

**Problem:** `_trigger_forum_sync()` exists as a stub that does nothing, misleading readers into thinking forum sync is triggered by task mutations.

**Fix (Option A — wire it up):** Inject the `ForumSyncService` singleton into `TaskService` and call it from `_trigger_forum_sync()`.

**Fix (Option B — remove dead code):** Delete `_trigger_forum_sync()` entirely and add a comment explaining the sync is triggered by the Discord bot's polling loop, not by TaskService.

---

### CLI-65 — Legacy Task-Master.py (1493-line Tkinter desktop app) needs triage

**File:** `Task-Master.py`  
**Priority:** LOW

**Problem:** The root-level `Task-Master.py` is a legacy Tkinter desktop app with 15+ silent exception handlers (`except: pass`), 1493 lines, and duplicate class definitions. It is not part of the deployed services but adds confusion.

**Options:**
1. **Archive** — move to `archive/Task-Master.py` with a README note
2. **Delete** — if no one actively uses the desktop app
3. **Separate repo** — if it should be maintained independently

**Recommended:** Confirm with George/Kobii whether the desktop app is still used. If not, delete it. If it is, move to `archive/`.

---

## MEDIUM — Discord Bot Correctness

### CLI-59 — Synchronous blocking calls in async context (paste_service)

**File:** `discord_bot/services/paste_service.py`, anywhere `offload_description()` is called from async handlers  
**Priority:** MEDIUM

**Problem:** `offload_description()` is a blocking function (does DNS lookup + HTTP request). Calling it directly from Discord.py async callbacks blocks the asyncio event loop, which can cause the bot to miss heartbeats and get disconnected.

**Fix:** The async wrappers `async_offload_description()` and `async_upload_to_paste()` are already implemented in `paste_service.py`. Use them everywhere in async contexts:

```python
# Search for synchronous calls in async handlers:
grep -rn "offload_description\|upload_to_paste" discord_bot/ | grep -v "async_"

# Replace:
# WRONG (in async handler):
url = offload_description(description, title)

# CORRECT:
url = await async_offload_description(description, title)
```

Check these files specifically:
- `discord_bot/discord_ui/modals.py` — modal `on_submit` handlers
- `discord_bot/services/logging_service.py` — log event handlers
- `discord_bot/discord_ui/buttons.py` — button callbacks

---

### CLI-60 — Raw Python exceptions leaked to Discord users

**File:** `discord_bot/discord_ui/buttons.py`, `discord_bot/discord_ui/modals.py`, `discord_bot/bot.py`  
**Priority:** MEDIUM

**Problem:** Exception handlers send the raw exception message to Discord, e.g.:
```python
await interaction.followup.send(f"Error: {e}")
```

This exposes internal details (file paths, variable values, API URLs) to users.

**Fix:** Log the full exception, send a generic user-facing message:

```python
# WRONG:
except Exception as e:
    await interaction.followup.send(f"Error: {e}")

# CORRECT:
except Exception as e:
    logger.error(f"Button handler error for {interaction.user}: {e}", exc_info=True)
    await interaction.followup.send(
        "❌ Something went wrong. Please try again or contact an admin.",
        ephemeral=True
    )
```

---

### CLI-206 / CLI-205 — Bare `except Exception as e: pass` silently swallows errors (11 instances)

**Files:** `discord_bot/bot.py:329`, `discord_bot/discord_ui/buttons.py:19`, `discord_bot/discord_ui/modals.py:48`, `discord_bot/services/forum_sync_service.py:379`  
**Priority:** MEDIUM / LOW

**Fix:** Replace all bare `except Exception: pass` with logged handlers:

```python
# WRONG:
except Exception:
    pass

# CORRECT:
except Exception as e:
    logger.error(f"Unexpected error in <context>: {e}", exc_info=True)
    # Take appropriate action (retry, notify, skip safely)
```

Find all instances:
```bash
grep -rn "except Exception:\s*$\|except Exception as.*pass" discord_bot/
```

---

### CLI-63 — Type annotation mismatch: REMINDER_CHANNEL: int = None

**File:** `discord_bot/config/settings.py`  
**Priority:** LOW

**Problem:** `REMINDER_CHANNEL: int = None` is invalid — `None` is not an `int`.

**Fix:**
```python
from typing import Optional

# WRONG:
REMINDER_CHANNEL: int = None

# CORRECT:
REMINDER_CHANNEL: Optional[int] = None
```

---

### CLI-207 — DISCORD_BOT_TOKEN defaults to empty string

**File:** `discord_bot/config/settings.py`  
**Priority:** LOW

**Problem:** If `DISCORD_BOT_TOKEN` is not set, the bot silently tries to connect with an empty string token, resulting in a confusing `LoginFailure` instead of a clear startup error.

**Fix:** Fail fast at startup:

```python
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', '')
if not DISCORD_BOT_TOKEN:
    raise RuntimeError("DISCORD_BOT_TOKEN is required — set it in discord_bot/.env")
```

---

### CLI-341 — Bare except in forum_sync_service.py:379 swallows channel fetch error

**File:** `discord_bot/services/forum_sync_service.py` line 379  
**Priority:** LOW

**Fix:**
```python
# WRONG (line ~379):
except Exception:
    pass  # silently ignores channel fetch failure

# CORRECT:
except discord.NotFound:
    logger.warning(f"Forum channel not found (ID: {channel_id}) — skipping sync")
except discord.Forbidden:
    logger.error(f"Missing permissions to access forum channel {channel_id}")
except Exception as e:
    logger.error(f"Unexpected error fetching channel {channel_id}: {e}", exc_info=True)
```

---

## MEDIUM — Datetime / Timezone Correctness

### CLI-147 — reminder_service uses naive datetime (timezone-unaware)

**File:** `discord_bot/services/reminder_service.py` lines 91, 98, 105–108  
**Priority:** MEDIUM

**Problem:** `datetime.now()` returns a naive datetime (no timezone info). If the server timezone changes or task deadlines are stored in UTC, comparisons will be incorrect.

**Fix:** Use timezone-aware datetimes throughout:

```python
from datetime import datetime, timedelta, timezone

# WRONG:
time_until_deadline = task.deadline_datetime - datetime.now()
overdue_key = f"{reminder_key}:overdue:{datetime.now().date()}"

# CORRECT:
_now = datetime.now(tz=timezone.utc)
time_until_deadline = task.deadline_datetime.astimezone(timezone.utc) - _now
overdue_key = f"{reminder_key}:overdue:{_now.date()}"
```

Also ensure `task.deadline_datetime` is always timezone-aware when parsed. Update `Task.deadline_datetime` property in `discord_bot/database/task_model.py` to parse with `tzinfo=timezone.utc` if no timezone is present.

---

### CLI-148 — reminded_tasks set grows unbounded (memory leak)

**File:** `discord_bot/services/reminder_service.py`  
**Priority:** MEDIUM

**Problem:** `self.reminded_tasks` accumulates reminder keys forever. Over months, this grows large and is serialized to Firebase on every check.

**Fix:** Prune old reminder keys periodically. Since keys include the date (`overdue:<date>`), purge entries older than N days:

```python
def _prune_reminded_tasks(self, keep_days: int = 30):
    """Remove reminder records older than keep_days days."""
    from datetime import date
    cutoff = date.today() - timedelta(days=keep_days)
    to_remove = set()
    for key in self.reminded_tasks:
        # Keys with date suffix: "owner:id:deadline:overdue:YYYY-MM-DD"
        parts = key.split(':')
        for part in parts:
            try:
                key_date = date.fromisoformat(part)
                if key_date < cutoff:
                    to_remove.add(key)
                    break
            except ValueError:
                continue
    if to_remove:
        self.reminded_tasks -= to_remove
        self._save_reminded_tasks()
        logger.info(f"Pruned {len(to_remove)} old reminder records")

# Call during the periodic check:
async def check_and_send_reminders(self):
    self._prune_reminded_tasks()
    # ... rest of method
```

---

## LOW — Error Handling & Silent Failures

### CLI-150 — TaskService mixes sync and async (get_all_tasks is sync)

**File:** `discord_bot/services/task_service.py`  
**Priority:** LOW

**Problem:** `get_all_tasks()` is a synchronous method while most other `TaskService` methods are async. Calling it from an async context blocks the event loop.

**Fix:** Make `get_all_tasks()` async, or wrap the blocking Firebase call in `asyncio.to_thread()`:

```python
import asyncio

async def get_all_tasks(self) -> List[Task]:
    """Async-safe task list fetch."""
    return await asyncio.to_thread(self._load_tasks_sync)

def _load_tasks_sync(self) -> List[Task]:
    """Blocking Firebase fetch — run via asyncio.to_thread only."""
    # ... existing sync Firebase load logic
```

---

### CLI-149 — Desktop app uses blocking time.sleep in UI thread

**File:** `Task-Master.py`  
**Priority:** LOW  
**Note:** Only relevant if the desktop Tkinter app is still being maintained.

**Fix:** Replace `time.sleep()` in Tkinter UI thread with `root.after(ms, callback)`:

```python
# WRONG — blocks UI:
time.sleep(30)
self.refresh()

# CORRECT — non-blocking Tkinter scheduler:
self.root.after(30000, self.refresh)
```

---

## LOW — Code Quality & Dead Code

### CLI-340 — Legacy Task-Master.py has 15 silent exception handlers

**File:** `Task-Master.py`  
**Priority:** MEDIUM

```bash
grep -n "except.*pass\|except:$" Task-Master.py
```

Each `except: pass` hides a potential bug. For each one: determine if the exception is truly ignorable. If yes, add a comment explaining why. If no, add a logger.error call.

---

### CLI-151 — Desktop app uses task name as database key (renames break references)

**File:** `Task-Master.py`  
**Priority:** LOW  
**Same root cause as CLI-339/CLI-263 in the web app.**

Fix: Use UUIDs as keys (same approach as web app fix above).

---

### CLI-152 — Startup script downloads Tailscale binaries at runtime

**Priority:** LOW

**Fix:** Pre-install Tailscale in the Docker image or deployment environment. Do not `curl | sh` at runtime — this is a supply chain attack vector.

---

### CLI-204 — Inconsistent KODA_PASTE_URL defaults between web app and discord bot

**Files:** `web_app/app.py` line 36 (defaults to `http://100.123.59.91:8845`), `discord_bot/services/paste_service.py` (defaults to `https://koda-vps.tail9ac53b.ts.net:8844`)  
**Priority:** MEDIUM

**Problem:** Web app uses HTTP port 8845; Discord bot defaults to HTTPS port 8844. The bot cannot reach the paste service via HTTPS without a working Tailscale DNS setup; the web app uses the IP directly.

**Fix:** Standardise both to use the env var. Do NOT hardcode any IP or hostname.

```python
# Both should use:
_PASTE_URL = os.environ.get("KODA_PASTE_URL")
if not _PASTE_URL:
    logger.warning("KODA_PASTE_URL not configured — description offload disabled")
```

Set `KODA_PASTE_URL=http://100.123.59.91:8845` in both `.env` files.

---

### CLI-416 / CLI-437 — Hardcoded Tailscale IP in _is_paste_url()

**File:** `web_app/app.py` — `_is_paste_url()` function  
**Priority:** LOW

**Problem:** `_is_paste_url()` hardcodes `100.123.59.91` and `tail9ac53b.ts.net`. If the Tailscale IP or hostname changes, paste URLs won't be recognised.

**Fix:** Derive the check from the configured `KODA_PASTE_URL`:

```python
def _is_paste_url(value: str) -> bool:
    """Return True if value is a koda-paste share URL, derived from KODA_PASTE_URL config."""
    if not value or not _PASTE_BASE:
        return False
    # A paste URL starts with the configured base and contains /p/
    return value.startswith(_PASTE_BASE) and "/p/" in value
```

---

## LOW — Logging & Observability

### CLI-154 — Log file grows unbounded (no rotation configured)

**File:** `web_app/app.py`  
**Priority:** LOW

**Problem:** `logging.basicConfig(level=logging.INFO)` logs to stdout/stderr only, which Gunicorn captures to a file that grows forever.

**Fix:** Add a rotating file handler:

```python
from logging.handlers import RotatingFileHandler
import os

_log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO)
_log_path = os.getenv('LOG_FILE', '/tmp/task-master.log')
_max_bytes = int(os.getenv('LOG_MAX_BYTES', str(10 * 1024 * 1024)))  # 10MB
_backup_count = int(os.getenv('LOG_BACKUP_COUNT', '5'))

logging.basicConfig(
    level=_log_level,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    handlers=[
        RotatingFileHandler(_log_path, maxBytes=_max_bytes, backupCount=_backup_count),
        logging.StreamHandler(),  # Also log to stdout for systemd journal
    ]
)
logger = logging.getLogger(__name__)
```

---

## IN REVIEW

### CLI-298 — Zero test files in the entire codebase

**Priority:** HIGH  
**Status:** In Review (some test infrastructure work started)

**What's needed:** Basic test coverage for the most critical paths:

1. `test_auth.py` — login requires password, CSRF token checked, session cookie flags set
2. `test_api.py` — create_task/update_task validation, 404 on missing task, error messages are generic
3. `test_security.py` — timing attack fix (compare_digest), XSS via URL rejected, IP whitelist not bypassable via X-Forwarded-For
4. `test_discord_bot.py` — normalize_subtasks, Task model round-trip, reminder pruning

```bash
# Add to web_app/requirements.txt (test dependencies):
pytest==8.3.0
pytest-flask==1.3.0
pytest-mock==3.14.0

# Create test structure:
mkdir -p tests/
touch tests/__init__.py tests/conftest.py
touch tests/test_auth.py tests/test_api.py tests/test_security.py
```

Example `tests/conftest.py`:
```python
import pytest
from web_app.app import app as flask_app

@pytest.fixture
def app():
    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret',
        'WTF_CSRF_ENABLED': False,  # Disable CSRF for test client
    })
    yield flask_app

@pytest.fixture
def client(app):
    return app.test_client()
```

---

## POST-Migration Verification Checklist

After all changes are implemented and deployed, verify the following:

### Security

- [ ] `curl -I https://task-master.clickdns.com.au` — confirm `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options` headers are present
- [ ] `curl -X POST https://task-master.clickdns.com.au/login -d 'username=admin'` — should fail (no password provided)
- [ ] `curl -X POST https://task-master.clickdns.com.au/login -d 'username=admin&password=wrong'` — should return login error, NOT a session cookie
- [ ] `curl -X POST https://task-master.clickdns.com.au/login -d 'username=admin&password=wrong' -H 'X-Forwarded-For: 127.0.0.1'` — IP whitelist should NOT be bypassed
- [ ] `curl -X POST https://task-master.clickdns.com.au/api/tasks` — should return 401 (not logged in), not 500
- [ ] Confirm `credentials.json` is NOT present in the repo root (`ls credentials.json` → should say no such file)
- [ ] Confirm `git log --all --full-history -- credentials.json` shows no commits (after history purge)
- [ ] Confirm session cookie has `Secure`, `HttpOnly`, `SameSite=Lax` flags (browser DevTools → Application → Cookies)

### Functionality

- [ ] Web app login page shows password field
- [ ] Login with correct password works
- [ ] Login with wrong password fails with generic error
- [ ] Create task with unique name → creates with UUID id, not name-based key
- [ ] Create task with duplicate name → creates a SECOND separate task (no silent overwrite)
- [ ] Update non-existent task → returns 404 (not 200)
- [ ] POST `/api/tasks` with no body → returns 400 (not 500)
- [ ] Subtask endpoints work: add, edit, toggle, delete
- [ ] Discord bot reminder fires and uses timezone-aware comparison
- [ ] `/refresh` Discord command blocked for non-admins

### Dependencies

- [ ] `pip check` in venv shows no dependency conflicts
- [ ] `pip install --require-hashes -r requirements.txt` succeeds (after hash pinning)
- [ ] `gunicorn --version` shows 23.x
- [ ] `python3 -c "import werkzeug; print(werkzeug.__version__)"` shows 3.1.6+

### Logging

- [ ] Log file at configured path is writing
- [ ] Log rotation kicks in at 10MB (verify `ls -la /tmp/task-master.log*`)
- [ ] Error responses do NOT contain `str(e)` exception details (check with an intentionally bad request)

---

## Issue Index (All 83 Open Issues)

| ID | Priority | Status | Title |
|----|----------|--------|-------|
| CLI-132 | URGENT | Todo | CRITICAL: credentials.json committed to git |
| CLI-135 | URGENT | Todo | CRITICAL: Web app has no authentication |
| CLI-196 | URGENT | Todo | Flask debug mode enabled — Werkzeug debugger exposed |
| CLI-288 | URGENT | Backlog | Minor upgrade for h11 |
| CLI-291 | URGENT | Backlog | Flask app debug mode may allow remote code execution |
| CLI-344 | URGENT | Backlog | Minor upgrade for aiohttp |
| CLI-57 | URGENT | Todo | Security: web app login has zero authentication |
| CLI-137 | HIGH | Todo | Hardcoded fallback secret key in web app |
| CLI-139 | HIGH | Todo | Carbon API key comparison vulnerable to timing attack |
| CLI-140 | HIGH | Todo | No CSRF protection on web app |
| CLI-197 | HIGH | Todo | No password authentication — any username can log in |
| CLI-198 | HIGH | Todo | Weak default Flask secret key hardcoded in source |
| CLI-199 | HIGH | Todo | X-Forwarded-For header trusted without proxy validation |
| CLI-250 | HIGH | Todo | X-Forwarded-For header used for IP whitelist check — bypassable |
| CLI-251 | HIGH | Todo | Firebase path injection via task name used as database key |
| CLI-252 | HIGH | Todo | requirements.txt missing core runtime dependencies |
| CLI-285 | HIGH | Todo | X-Forwarded-For header spoofable for IP whitelist bypass |
| CLI-298 | HIGH | In Review | Zero test files in the entire codebase |
| CLI-331 | HIGH | Todo | web_app/.env with production credentials not protected by .gitignore |
| CLI-332 | HIGH | Todo | No CSRF protection on any state-changing endpoint |
| CLI-333 | HIGH | Todo | str(e) in all API error responses leaks internal exception details |
| CLI-334 | HIGH | Todo | create_task() and update_task() crash if JSON body missing |
| CLI-377 | HIGH | Backlog | Major upgrade for gunicorn |
| CLI-378 | HIGH | Backlog | 7 exposed secrets |
| CLI-386 | HIGH | Todo | Tailscale auth key co-located with app runtime secrets |
| CLI-429 | HIGH | Todo | Flask SECRET_KEY has weak hardcoded fallback |
| CLI-430 | HIGH | Todo | Root .gitignore does not exclude .env files |
| CLI-438 | HIGH | Backlog | Potential XSS via window.location.href (ClickDNS) |
| CLI-439 | HIGH | Backlog | Minor upgrade for Werkzeug |
| CLI-440 | HIGH | Backlog | CSP policy does not block eval() |
| CLI-58 | HIGH | Todo | Security: /refresh slash command not gated to admins/owners |
| CLI-141 | MEDIUM | Todo | Race condition: full task list read-modify-write |
| CLI-142 | MEDIUM | Todo | normalize_subtasks duplicated 4 times |
| CLI-143 | MEDIUM | Todo | Task class duplicated in Task-Master.py vs discord_bot |
| CLI-144 | MEDIUM | Todo | Unpinned dependencies with known CVE exposure |
| CLI-145 | MEDIUM | Todo | No tests exist for any component |
| CLI-146 | MEDIUM | Todo | ForumSyncService creates new instances on every button interaction |
| CLI-147 | MEDIUM | Todo | reminder_service uses naive datetime — timezone-unaware |
| CLI-148 | MEDIUM | Todo | reminded_tasks set grows unbounded — memory leak |
| CLI-200 | MEDIUM | Todo | Root .env committed to git — not in .gitignore |
| CLI-201 | MEDIUM | Todo | Non-constant-time API key comparison — timing attack |
| CLI-202 | MEDIUM | Todo | Missing null-check on request.get_json() in API endpoints |
| CLI-203 | MEDIUM | Todo | Session cookies missing Secure and SameSite flags |
| CLI-204 | MEDIUM | Todo | Inconsistent KODA_PASTE_URL defaults between web app and bot |
| CLI-205 | MEDIUM | Todo | 11 bare except Exception pass blocks silently swallow errors |
| CLI-260 | MEDIUM | Todo | Internal exception messages exposed in all API error responses |
| CLI-261 | MEDIUM | Todo | Non-constant-time API key comparison enables timing attack |
| CLI-262 | MEDIUM | Todo | No URL field validation (javascript: URLs accepted) |
| CLI-263 | MEDIUM | Todo | Duplicate task names silently overwrite each other in Firebase |
| CLI-269 | MEDIUM | Todo | update_task returns HTTP 200 when task_id doesn't exist |
| CLI-270 | MEDIUM | Todo | create_task crashes with KeyError 500 if name field missing |
| CLI-271 | MEDIUM | Todo | SESSION_TYPE=filesystem set but Flask-Session not installed |
| CLI-335 | MEDIUM | Todo | IP whitelist bypassable via X-Forwarded-For spoofing |
| CLI-336 | MEDIUM | Todo | Non-constant-time CARBON_API_KEY comparison — timing oracle |
| CLI-337 | MEDIUM | Todo | No rate limiting on any endpoint |
| CLI-338 | MEDIUM | Todo | CORS_ORIGINS env var configured but Flask-CORS not installed |
| CLI-339 | MEDIUM | Todo | Task ID set to task name — silent overwrite on duplicate names |
| CLI-340 | MEDIUM | Todo | Legacy Task-Master.py — 15 silent exception handlers and dead code |
| CLI-403 | MEDIUM | Todo | Flask SECRET_KEY has weak hardcoded fallback default |
| CLI-404 | MEDIUM | Todo | Flask app has no HTTP security headers |
| CLI-405 | MEDIUM | Todo | Session cookie missing Secure, HttpOnly, SameSite flags |
| CLI-406 | MEDIUM | Todo | Root .gitignore relies solely on nested gitignore |
| CLI-59 | MEDIUM | Todo | Synchronous blocking calls in async context (paste_service) |
| CLI-60 | MEDIUM | Todo | Raw Python exceptions leaked to Discord users |
| CLI-149 | LOW | Todo | Desktop app uses blocking time.sleep in UI thread |
| CLI-150 | LOW | Todo | TaskService mixes sync and async — get_all_tasks() is sync |
| CLI-151 | LOW | Todo | Desktop app uses task name as database key |
| CLI-152 | LOW | Todo | Web app startup script downloads binaries at runtime |
| CLI-153 | LOW | Todo | No input length limits on web app API endpoints |
| CLI-154 | LOW | Todo | Log file grows unbounded — no rotation configured |
| CLI-206 | LOW | Todo | Bare except Exception in discord_bot auto-delete silently fails |
| CLI-207 | LOW | Todo | DISCORD_BOT_TOKEN defaults to empty string |
| CLI-272 | LOW | Todo | Root .env committed to git — audit history |
| CLI-341 | LOW | Todo | Bare except in forum_sync_service.py:379 swallows error |
| CLI-416 | LOW | Todo | Hardcoded Tailscale IP in _is_paste_url() — fragile |
| CLI-417 | LOW | Todo | SESSION_TYPE=filesystem set but Flask-Session not installed |
| CLI-437 | LOW | Todo | Hardcoded Tailscale IP 100.123.59.91 in _is_paste_url() |
| CLI-61 | LOW | Todo | Duplicate sync orchestration logic across 7+ handlers |
| CLI-62 | LOW | Todo | _trigger_forum_sync() is a dead no-op stub in TaskService |
| CLI-63 | LOW | Todo | Type annotation mismatch: REMINDER_CHANNEL: int = None |
| CLI-64 | LOW | Todo | ForumSyncService re-instantiated on every interaction |
| CLI-65 | LOW | Todo | Legacy Task-Master.py root file (1493 lines) needs triage |
| CLI-373 | NO PRIORITY | Todo | web_app/.env with live secrets committed to git |

---

*End of COPILOT-ISSUES.md — generated 2026-03-07 from Linear team CLI*
