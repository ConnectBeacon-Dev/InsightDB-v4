# ConnectBeacon AI Chatbot - Integration Guide

**Simple guide for integrating the chatbot into your existing website or deploying standalone.**

---

## Table of Contents

1. [Quick Start - Standalone Deployment](#quick-start---standalone-deployment)
2. [Integration - Add Chatbot Button to Existing Website](#integration---add-chatbot-button-to-existing-website)
3. [Configuration Reference](#configuration-reference)
4. [Server Management](#server-management)

---

## Quick Start - Standalone Deployment

### Step 1: Deploy the Chatbot

```bash
# One command - generates secrets automatically
python deploy_production.py
```

### Step 2: Configure Nginx (for HTTPS)

See `nginx.conf` example in `docs/deploy/nginx.conf`

### Step 3: Access

- **Login**: https://login.connectbeacon.com
- **Chatbot**: https://chat.connectbeacon.com/aichat/

**That's it!** The chatbot is now running standalone.

---

## Integration - Add Chatbot Button to Existing Website

### Scenario 1: Simple Button (No SSO)

Add this to your existing website:

```html
<!-- Chatbot Button -->
<button onclick="openChatbot()">💬 Ask AI Assistant</button>

<script>
function openChatbot() {
    // Open chatbot in new window
    window.open('https://chat.connectbeacon.com/aichat/', 
                'chatbot', 
                'width=400,height=600');
}
</script>
```

**Done!** Users click the button and get a standalone login page.

---

### Scenario 2: Seamless SSO Integration

If you want users to access the chatbot **without a separate login**, integrate with SSO:

#### Step 1: Generate SSO Token in Your Backend

**Python Example:**
```python
import jwt
import time

def generate_chatbot_token(user_id, name, email):
    """Generate SSO token for chatbot"""
    
    # Get shared secret from environment
    secret = os.environ['SSO_SHARED_SECRET']
    
    payload = {
        'sub': user_id,           # User ID
        'name': name,             # Full name
        'email': email,           # Email
        'iss': 'ddpdashboard-aichatbot-portal',  # Your app name
        'aud': 'aichat',          # Must be 'aichat'
        'iat': int(time.time()),
        'exp': int(time.time()) + 3600  # 1 hour expiry
    }
    
    token = jwt.encode(payload, secret, algorithm='HS256')
    return token
```

**Node.js Example:**
```javascript
const jwt = require('jsonwebtoken');

function generateChatbotToken(userId, name, email) {
    const secret = process.env.SSO_SHARED_SECRET;
    
    const payload = {
        sub: userId,
        name: name,
        email: email,
        iss: 'ddpdashboard-aichatbot-portal',
        aud: 'aichat',
        iat: Math.floor(Date.now() / 1000),
        exp: Math.floor(Date.now() / 1000) + 3600
    };
    
    return jwt.sign(payload, secret, { algorithm: 'HS256' });
}
```

#### Step 2: Add Button to Your Website

```html
<!-- Chatbot Button -->
<button onclick="openChatbotSSO()">💬 Ask AI Assistant</button>

<script>
async function openChatbotSSO() {
    // Get SSO token from your backend
    const response = await fetch('/api/chatbot-token');
    const data = await response.json();
    
    // Open chatbot with SSO token
    const url = `https://chat.connectbeacon.com/aichat/sso?token=${data.token}`;
    window.open(url, 'chatbot', 'width=400,height=600');
}
</script>
```

#### Step 3: Create Backend Endpoint

**Python/Flask:**
```python
@app.route('/api/chatbot-token')
def chatbot_token():
    # Get current user from session
    user = get_current_user()
    
    # Generate token
    token = generate_chatbot_token(
        user_id=user.id,
        name=user.name,
        email=user.email
    )
    
    return {'token': token}
```

**Node.js/Express:**
```javascript
app.get('/api/chatbot-token', (req, res) => {
    // Get current user from session
    const user = req.user;
    
    // Generate token
    const token = generateChatbotToken(
        user.id,
        user.name,
        user.email
    );
    
    res.json({ token });
});
```

**Done!** Users are automatically logged into the chatbot.

---

### Scenario 3: Embedded iFrame

Embed the chatbot directly in your page:

```html
<!-- Chatbot Container -->
<div id="chatbot-container" style="display:none; position:fixed; bottom:20px; right:20px; width:400px; height:600px; border:1px solid #ccc; border-radius:8px; box-shadow:0 4px 12px rgba(0,0,0,0.15); background:white; z-index:9999;">
    <div style="display:flex; justify-content:space-between; padding:10px; background:#007bff; color:white; border-radius:8px 8px 0 0;">
        <span>AI Assistant</span>
        <button onclick="closeChatbot()" style="background:none; border:none; color:white; cursor:pointer; font-size:20px;">&times;</button>
    </div>
    <iframe id="chatbot-iframe" style="width:100%; height:calc(100% - 50px); border:none;"></iframe>
</div>

<!-- Floating Button -->
<button onclick="toggleChatbot()" style="position:fixed; bottom:20px; right:20px; width:60px; height:60px; border-radius:50%; background:#007bff; color:white; border:none; font-size:24px; cursor:pointer; box-shadow:0 4px 12px rgba(0,0,0,0.3); z-index:9998;">
    💬
</button>

<script>
let chatbotOpen = false;

async function toggleChatbot() {
    const container = document.getElementById('chatbot-container');
    const iframe = document.getElementById('chatbot-iframe');
    
    if (!chatbotOpen) {
        // Get SSO token
        const response = await fetch('/api/chatbot-token');
        const data = await response.json();
        
        // Load chatbot with SSO
        iframe.src = `https://chat.connectbeacon.com/aichat/sso?token=${data.token}`;
        container.style.display = 'block';
        chatbotOpen = true;
    } else {
        closeChatbot();
    }
}

function closeChatbot() {
    document.getElementById('chatbot-container').style.display = 'none';
    chatbotOpen = false;
}
</script>
```

---

## Configuration Reference

### Environment Variables (`.env.production`)

```env
# Required: Shared secret for JWT signing (auto-generated)
SSO_SHARED_SECRET=<64-character-secret>

# URLs
CHATBOT_URL=https://chat.connectbeacon.com/aichat/sso
LOGIN_URL=https://login.connectbeacon.com

# Server Configuration
SERVER_HOST=0.0.0.0
PORT=8000
LOGIN_PORT=5000

# SSO Configuration
SSO_EXPECT_ISS=ddpdashboard-aichatbot-portal
SSO_EXPECT_AUD=aichat
TOKEN_EXPIRY=3600
```

### Key Configuration Points

| Setting | Purpose | Default |
|---------|---------|---------|
| `SSO_SHARED_SECRET` | JWT signing key (must match in your backend) | Auto-generated |
| `SSO_EXPECT_ISS` | Issuer name (your app identifier) | `ddpdashboard-aichatbot-portal` |
| `SSO_EXPECT_AUD` | Audience (must be `aichat`) | `aichat` |
| `TOKEN_EXPIRY` | Token validity in seconds | `3600` (1 hour) |

---

## Server Management

### Start Servers
```bash
python deploy_production.py
```

### Stop Servers
```bash
python stop_servers.py
```

### View Logs
```bash
# Windows PowerShell
Get-Content logs\chatbot_server.out -Tail 50

# Linux/Mac
tail -f logs/chatbot_server.out
```

### Check Status
```bash
# Check if servers are running
netstat -ano | findstr "8000 5000"  # Windows
lsof -i :8000 -i :5000              # Linux/Mac
```

---

## Migration Checklist

Moving to a new server or environment?

- [ ] Copy `.env.production` (contains your secret)
- [ ] Install Python dependencies: `pip install -r requirements.txt`
- [ ] Run deployment: `python deploy_production.py`
- [ ] Configure nginx with SSL certificates
- [ ] Update DNS records if needed
- [ ] Test SSO token generation in your backend
- [ ] Verify chatbot access

---

## Troubleshooting

### JWT Verification Failed

**Symptom:** "Invalid token" or "Signature verification failed"

**Solution:**
1. Ensure `SSO_SHARED_SECRET` is the same in:
   - `.env.production` (chatbot server)
   - Your backend code (token generation)
2. Restart servers after changing secret: `python stop_servers.py && python deploy_production.py`

### Chatbot Not Loading

**Check:**
1. Servers running: `Get-Content logs\server.pids`
2. Nginx running and configured correctly
3. Firewall allows ports 443, 8000, 5000
4. DNS resolves to correct IP

### CORS Issues (iFrame)

If embedding in iFrame, ensure your domain is allowed. Contact support to whitelist your domain.

---

## Support

For issues or questions:
1. Check logs: `logs/chatbot_server.out` and `logs/login_server.out`
2. Review this guide
3. Contact your system administrator

---

**Last Updated:** October 2025
