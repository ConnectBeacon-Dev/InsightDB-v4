# Configuration Guide - Centralized URLs

## Overview

All URLs are now centralized in **`config.yaml`** for easy management. Change URLs in one place and they apply everywhere.

---

## Configuration Priority

The system uses this priority order:

1. **Environment variables** (highest priority)
2. **config.yaml** (middle priority)
3. **Default values** (fallback)

---

## config.yaml - URL Configuration

```yaml
# Production URLs - Change these for your deployment
urls:
  login: "https://login.connectbeacon.com"
  chatbot: "https://chat.connectbeacon.com/aichat"
  chatbot_sso: "https://chat.connectbeacon.com/aichat/sso"
```

### To Change URLs

**Option 1: Edit config.yaml (Recommended)**

```yaml
urls:
  login: "https://login.yourdomain.com"
  chatbot: "https://chat.yourdomain.com/aichat"
  chatbot_sso: "https://chat.yourdomain.com/aichat/sso"
```

**Option 2: Use Environment Variables**

```bash
export LOGIN_URL="https://login.yourdomain.com"
export CHATBOT_URL="https://chat.yourdomain.com/aichat"
```

---

## Complete config.yaml Reference

```yaml
# Production URLs - Change these for your deployment
urls:
  login: "https://login.connectbeacon.com"
  chatbot: "https://chat.connectbeacon.com/aichat"
  chatbot_sso: "https://chat.connectbeacon.com/aichat/sso"

# SSO Configuration
sso:
  secret: null  # Set via SSO_SHARED_SECRET env var (auto-generated)
  expect_issuer: "ddpdashboard-aichatbot-portal"
  expect_audience: "aichat"
  portal_url: "http://127.0.0.1:7000/askme-sso"

# Cookie Configuration
cookie:
  name: "aichat_sid"
  domain: null  # null = current domain only
  secure: true  # true for HTTPS, false for HTTP
  samesite: "Lax"
  path: "/aichat"

# Session Timeouts (in seconds)
session:
  ttl_idle: 1800      # 30 minutes
  ttl_absolute: 28800 # 8 hours

# Redis Configuration
redis:
  url: "redis://127.0.0.1:6379/0"
  use_fake_redis: true  # true = in-memory, false = real Redis
```

---

## Common Scenarios

### Scenario 1: Change Domain Name

**Before:**
```yaml
urls:
  login: "https://login.connectbeacon.com"
  chatbot: "https://chat.connectbeacon.com/aichat"
  chatbot_sso: "https://chat.connectbeacon.com/aichat/sso"
```

**After:**
```yaml
urls:
  login: "https://login.mycompany.com"
  chatbot: "https://chat.mycompany.com/aichat"
  chatbot_sso: "https://chat.mycompany.com/aichat/sso"
```

**Steps:**
1. Edit `config.yaml`
2. Restart servers: `python stop_servers.py && python deploy_production.py`
3. Update nginx configuration with new domain
4. Done!

---

### Scenario 2: Development vs Production

**Development (config.yaml):**
```yaml
urls:
  login: "http://localhost:5000"
  chatbot: "http://localhost:8000/aichat"
  chatbot_sso: "http://localhost:8000/aichat/sso"

cookie:
  secure: false  # HTTP in dev
```

**Production (config.yaml):**
```yaml
urls:
  login: "https://login.connectbeacon.com"
  chatbot: "https://chat.connectbeacon.com/aichat"
  chatbot_sso: "https://chat.connectbeacon.com/aichat/sso"

cookie:
  secure: true  # HTTPS in production
```

---

### Scenario 3: Using Subpaths Instead of Subdomains

If you want to use paths instead of subdomains:

```yaml
urls:
  login: "https://connectbeacon.com/login"
  chatbot: "https://connectbeacon.com/chatbot"
  chatbot_sso: "https://connectbeacon.com/chatbot/sso"
```

Then update nginx to route:
- `/login` → port 5000
- `/chatbot` → port 8000

---

## Files That Read config.yaml

| File | What It Reads |
|------|---------------|
| `app_simple_login.py` | `urls.login`, `urls.chatbot_sso`, SSO config |
| `app_rag_chat_sso.py` | `urls.login`, `urls.chatbot`, SSO config, cookie config, session config |
| `deploy_production.py` | `urls.*` (to populate `.env.production`) |

---

## Migration from Old Setup

### Old Way (Hardcoded URLs)
```python
# Hardcoded in deploy_production.ps1
$env:CHATBOT_URL = "https://chat.connectbeacon.com/aichat/sso"
$env:LOGIN_URL = "https://login.connectbeacon.com"
```

### New Way (Centralized)
```yaml
# In config.yaml
urls:
  login: "https://login.connectbeacon.com"
  chatbot_sso: "https://chat.connectbeacon.com/aichat/sso"
```

**Benefits:**
- ✅ Change once, applies everywhere
- ✅ No need to edit multiple files
- ✅ Easy to switch between dev/prod
- ✅ Version controlled (config.yaml is committed)

---

## Environment Variable Override

You can still override URLs with environment variables:

```bash
# Override for testing
export LOGIN_URL="https://login-staging.connectbeacon.com"
export CHATBOT_URL="https://chat-staging.connectbeacon.com/aichat"

# Deploy
python deploy_production.py
```

This is useful for:
- Testing different environments
- CI/CD pipelines
- Temporary overrides

---

## Troubleshooting

### URLs Not Updating

**Problem:** Changed `config.yaml` but URLs still old

**Solution:**
1. Restart servers: `python stop_servers.py && python deploy_production.py`
2. Clear browser cache
3. Check `.env.production` was regenerated

### Wrong URL in Redirects

**Problem:** Login redirects to wrong chatbot URL

**Solution:**
1. Check `config.yaml` has correct `urls.chatbot_sso`
2. Verify environment variable not overriding: `echo $CHATBOT_URL`
3. Restart servers

### Mixed HTTP/HTTPS

**Problem:** Some URLs HTTP, some HTTPS

**Solution:**
Ensure all URLs in `config.yaml` use same protocol:
```yaml
urls:
  login: "https://login.connectbeacon.com"      # ✓ HTTPS
  chatbot: "https://chat.connectbeacon.com/aichat"  # ✓ HTTPS
  # NOT:
  # login: "http://login.connectbeacon.com"     # ✗ Mixed
```

---

## Best Practices

### 1. Keep config.yaml in Git
```bash
git add config.yaml
git commit -m "Update production URLs"
```

### 2. Don't Commit .env.production
```bash
# Already in .gitignore
.env.production  # Contains secrets
```

### 3. Document URL Changes
```yaml
# config.yaml
# Updated 2025-10-17: Changed to new domain
urls:
  login: "https://login.newdomain.com"
```

### 4. Test After Changes
```bash
# After changing config.yaml
python stop_servers.py
python deploy_production.py

# Test
curl https://login.connectbeacon.com
curl https://chat.connectbeacon.com/aichat/health
```

---

## Quick Reference

### Change URLs
1. Edit `config.yaml` → `urls` section
2. Restart: `python stop_servers.py && python deploy_production.py`
3. Test URLs

### View Current Config
```bash
cat config.yaml | grep -A 3 "urls:"
```

### Check What's Loaded
```bash
# Check environment
python -c "from app_simple_login import config; print(config)"
```

---

## Summary

**Single Source of Truth:** `config.yaml`

**To Change URLs:**
1. Edit `config.yaml`
2. Restart servers
3. Done!

**No need to edit:**
- ❌ `deploy_production.py`
- ❌ `app_simple_login.py`
- ❌ `app_rag_chat_sso.py`
- ❌ Multiple files

**Just edit:**
- ✅ `config.yaml` (one file!)

---

**Everything is now centralized and easy to manage!** 🎉
