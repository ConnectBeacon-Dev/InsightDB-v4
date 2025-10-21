# InsightDB AI Chatbot - Deployment Guide

## 🚀 Quick Start (3 Commands)

```powershell
# 1. Deploy (generates secret, starts servers)
python deploy.py

# 2. Test standalone login
Start http://localhost:5000/

# 3. Test embedded chatbot
Start http://localhost:8000/examples/chatbot_embedded_local.html
```

**That's it!** Both local and production use the same SSO flow.

---

## 📖 Documentation

| Document | When to Read |
|----------|-------------|
| **This file** | 👈 **Start here!** Quick deployment |
| [FINAL_SUMMARY.md](FINAL_SUMMARY.md) | Complete overview and architecture |
| [examples/README.md](examples/README.md) | Integration guide for embedded chatbot |

---

## 🎯 Two Integration Scenarios

### A) Embedded Chatbot (Your Webpage)
```
Your App → User logged in → Click chat button → 
/api/chatbot-token → JWT token → Chatbot opens → Auto-logged in ✓
```

**Example:** `https://chat.aichatbot.schemes.ddpdashboard.gov.in/examples/chatbot_embedded_production.html`

### B) Standalone Login Page
```
Login page → Enter credentials → Generate JWT → 
Redirect to chatbot → Validate JWT → Logged in ✓
```

**Example:** `http://localhost:5000/`

**Both use the SAME SSO flow!**

---

## 📁 Key Files

```
deploy.py                    ← ONE SCRIPT (run this!)
├── Generates .env.production (SSO secret)
├── Sets up virtual environment
└── Calls run_pipeline_and_serve.py
    ├── Starts login server (port 5000)
    └── Starts chatbot server (port 8000)

config.yaml                  ← SSO configuration
.env.production             ← SSO secret (auto-generated)

app_rag_chat_sso.py         ← Chatbot server
├── /api/chatbot-token      ← NEW: JWT token generator
├── /aichat/sso             ← SSO callback
└── /aichat/                ← Main chat interface

app_simple_login.py         ← Login server
```

---

## ⚡ Commands

```powershell
# Deploy
python deploy.py                    # Production (skips ETL)
python deploy.py --with-etl         # First time (runs ETL)
python deploy.py --dev              # Development (foreground)

# Manage
python stop_servers.py              # Stop servers
netstat -ano | findstr "8000 5000"  # Check if running

# Logs
Get-Content logs\chatbot_server.out -Tail 50
Get-Content logs\login_server.out -Tail 50
```

---

## 🔑 How SSO Works

```
┌──────────────────────────────────────────────────────────┐
│  1. User authenticates (login page OR your app)          │
│                         ↓                                │
│  2. Backend generates JWT token                          │
│     {sub: user_id, name: name, email: email}             │
│                         ↓                                │
│  3. Token passed to: /aichat/sso?token=JWT               │
│                         ↓                                │
│  4. Chatbot validates JWT using SSO_SHARED_SECRET        │
│                         ↓                                │
│  5. Session created in Redis → User logged in! ✓         │
└──────────────────────────────────────────────────────────┘
```

**Key:** Same secret (`.env.production`) used by both servers

---

## ✅ Success Checklist

- [ ] Run `python deploy.py`
- [ ] See "SERVERS STARTED SUCCESSFULLY!"
- [ ] Test standalone: `http://localhost:5000/`
- [ ] Test embedded: `http://localhost:8000/examples/chatbot_embedded_local.html`
- [ ] Both work without issues

---

## 🌐 Local vs Production

| Aspect | Local | Production |
|--------|-------|------------|
| **Command** | `python deploy.py` | `python deploy.py` |
| **Secret** | `.env.production` | `.env.production` |
| **Config** | `config.yaml` | `config.yaml` (update URLs) |
| **Cookie** | `secure: false` | `secure: true` |
| **URLs** | `localhost:5000/8000` | Your domain |

**Same script, same flow!** Just update `config.yaml` URLs for production.

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "SSO_SHARED_SECRET must be set" | Run `python deploy.py` (generates automatically) |
| "Authentication required" | Login first at `http://localhost:8000/aichat/` |
| Servers won't start | Check ports: `netstat -ano \| findstr "8000 5000"` |
| Can't access embedded chatbot | Must login first to establish session |

---

## 🎉 Ready to Deploy?

```powershell
python deploy.py
```

Then open: `http://localhost:5000/` 🚀
