# InsightDB Chatbot - Quick Integration Guide

## 5-Minute Integration

### Step 1: Add the Button to Your Webpage

Copy and paste this code into your HTML:

```html
<!-- Add before closing </body> tag -->
<a href="https://your-domain.com/aichat/" 
   class="ai-chatbot-btn" 
   target="_blank">
    💬 Ask AI Assistant
</a>

<style>
.ai-chatbot-btn {
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 14px 24px;
    border-radius: 50px;
    text-decoration: none;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-weight: 600;
    font-size: 15px;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    transition: all 0.3s ease;
    z-index: 1000;
    display: flex;
    align-items: center;
    gap: 8px;
}

.ai-chatbot-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
}
</style>
```

**Replace:** `https://your-domain.com/aichat/` with your actual chatbot URL.

### Step 2: Configure SSO (Backend)

Set the shared secret as an environment variable:

```bash
export SSO_SHARED_SECRET="your-secret-key-here"
```

### Step 3: Generate JWT Tokens (SSO Portal)

```python
import jwt
import time

def create_chatbot_token(user_id, user_name):
    return jwt.encode({
        "sub": user_id,
        "name": user_name,
        "iss": "your-portal-name",
        "aud": "aichat",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600
    }, "your-secret-key-here", algorithm="HS256")
```

### Step 4: Test

1. Click the chatbot button
2. User gets redirected to SSO (if not authenticated)
3. SSO generates token and redirects back
4. User sees chat interface

Done! ✅

---

## Button Variations

### Floating Icon Button

```html
<a href="https://your-domain.com/aichat/" class="ai-fab" target="_blank">
    <svg viewBox="0 0 24 24" fill="white" width="28" height="28">
        <path d="M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
    </svg>
</a>

<style>
.ai-fab {
    position: fixed;
    bottom: 24px;
    right: 24px;
    width: 56px;
    height: 56px;
    background: #2196F3;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(33, 150, 243, 0.4);
    transition: all 0.3s ease;
    z-index: 1000;
}

.ai-fab:hover {
    transform: scale(1.1);
    box-shadow: 0 6px 20px rgba(33, 150, 243, 0.6);
}
</style>
```

### Bottom Bar Button

```html
<div class="ai-bottom-bar">
    <span>Need help?</span>
    <a href="https://your-domain.com/aichat/" target="_blank">
        Chat with AI Assistant →
    </a>
</div>

<style>
.ai-bottom-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #1e293b;
    color: white;
    padding: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
    z-index: 1000;
}

.ai-bottom-bar a {
    background: #3b82f6;
    color: white;
    padding: 8px 20px;
    border-radius: 6px;
    text-decoration: none;
    font-weight: 600;
    transition: background 0.2s;
}

.ai-bottom-bar a:hover {
    background: #2563eb;
}
</style>
```

### Sidebar Button

```html
<a href="https://your-domain.com/aichat/" class="ai-sidebar" target="_blank">
    <span>💬</span>
    <span>AI Help</span>
</a>

<style>
.ai-sidebar {
    position: fixed;
    right: 0;
    top: 50%;
    transform: translateY(-50%) rotate(-90deg);
    transform-origin: right center;
    background: #10b981;
    color: white;
    padding: 12px 24px;
    text-decoration: none;
    font-weight: 600;
    border-radius: 8px 8px 0 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    display: flex;
    align-items: center;
    gap: 8px;
    z-index: 1000;
}

.ai-sidebar:hover {
    background: #059669;
}
</style>
```

---

## Configuration Reference

### Minimal config.yaml

```yaml
sso:
  secret: null  # Use SSO_SHARED_SECRET env var
  expect_issuer: "your-portal"
  expect_audience: "aichat"
  portal_url: "https://your-portal.com/sso"

cookie:
  name: "aichat_sid"
  secure: true
  path: "/aichat"

session:
  ttl_idle: 1800
  ttl_absolute: 28800

redis:
  use_fake_redis: true
```

### Environment Variables

```bash
# Required
SSO_SHARED_SECRET=your-secret-key

# Optional
PORTAL_SSO_URL=https://your-portal.com/sso
REDIS_URL=redis://localhost:6379/0
USE_FAKE_REDIS=false
```

---

## JWT Token Format

```json
{
  "sub": "user-123",
  "name": "John Doe",
  "email": "john@example.com",
  "iss": "your-portal",
  "aud": "aichat",
  "iat": 1234567890,
  "exp": 1234571490
}
```

**Required Claims:**
- `sub` - User ID (unique identifier)
- `iss` - Issuer (must match config)
- `aud` - Audience (must be "aichat")
- `exp` - Expiration timestamp

**Optional Claims:**
- `name` - Display name
- `email` - User email
- `iat` - Issued at timestamp

---

## Common Integration Patterns

### Pattern 1: Direct Link
User clicks → Opens chatbot in new tab

```html
<a href="https://your-domain.com/aichat/" target="_blank">Ask AI</a>
```

### Pattern 2: Same Page
User clicks → Navigates to chatbot

```html
<a href="https://your-domain.com/aichat/">Ask AI</a>
```

### Pattern 3: Popup Window
User clicks → Opens chatbot in popup

```html
<button onclick="window.open('https://your-domain.com/aichat/', 
                'chatbot', 'width=800,height=600')">
    Ask AI
</button>
```

### Pattern 4: Iframe Embed
Chatbot embedded in page

```html
<iframe src="https://your-domain.com/aichat/" 
        width="400" height="600" 
        style="border:none;border-radius:12px;">
</iframe>
```

---

## Testing

### Test Token Generator

```python
import jwt
import time

secret = "your-secret-key"
token = jwt.encode({
    "sub": "test-user",
    "name": "Test User",
    "iss": "your-portal",
    "aud": "aichat",
    "iat": int(time.time()),
    "exp": int(time.time()) + 3600
}, secret, algorithm="HS256")

print(f"Test URL: http://localhost:8000/aichat/sso?token={token}")
```

### Quick Test

1. Generate token with script above
2. Open URL in browser
3. Should see chat interface
4. Try sending a message

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Authentication Error | Check shared secret matches |
| Cookie not set | Verify domain and secure settings |
| Token expired | Increase expiration time |
| Redis error | Set `use_fake_redis: true` |
| CORS error | Add origin to CORS config |

---

## Production Checklist

- [ ] Set `SSO_SHARED_SECRET` environment variable
- [ ] Enable HTTPS (`cookie.secure: true`)
- [ ] Configure proper cookie domain
- [ ] Set up real Redis (not fakeredis)
- [ ] Configure CORS for your domains
- [ ] Test SSO flow end-to-end
- [ ] Implement backchannel logout
- [ ] Set up monitoring/logging
- [ ] Test session timeouts
- [ ] Verify token expiration

---

## Need More Details?

See the full [SSO_INTEGRATION_GUIDE.md](./SSO_INTEGRATION_GUIDE.md) for:
- Detailed architecture diagrams
- Security best practices
- Advanced integration methods
- Complete API reference
- Comprehensive troubleshooting

---

## Support

**Health Check:** `GET /aichat/health`

**Logs:** Check `logs/` directory

**Test File:** Use `sso_test_link.html` for local testing
