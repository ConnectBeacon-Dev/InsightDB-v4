# Examples Directory

This directory contains the production-ready embedded chatbot example with automatic SSO login.

## File

- **`chatbot_embedded_production.html`** - Production embedded chatbot with auto-login

## 🚀 Quick Start

### 1. Deploy the Server

```bash
python deploy.py
```

This starts both login and chatbot servers with HTTPS support.

### 2. Access the Example

Open in your browser:
```
https://chat.aichatbot.schemes.ddpdashboard.gov.in/examples/chatbot_embedded_production.html
```

### 3. Test the Chatbot

- Click the 💬 button in the bottom-right corner
- Chatbot opens automatically without login prompt
- Start chatting!

---

## 🔧 How It Works

### Auto-Login Flow

```
1. User clicks 💬 button on your webpage
   ↓
2. JavaScript calls /api/chatbot-login with user details
   {user_id, name, email}
   ↓
3. Server creates session + returns JWT token
   ↓
4. Iframe loads /aichat/sso?token=JWT
   ↓
5. SSO validates token, creates session in iframe
   ↓
6. Chatbot opens - user is logged in! ✓
```

### Key Features

✅ **No separate login page** - User details passed directly  
✅ **HTTPS + SameSite=None** - Cookies work in iframes  
✅ **Floating chat button** - Modern UI  
✅ **Responsive design** - Works on mobile  
✅ **Auto token generation** - Seamless authentication  

---

## 📝 Integration into Your Website

### Step 1: Update User Details

Edit `chatbot_embedded_production.html` (lines 166-170):

```javascript
const USER_DETAILS = {
    user_id: "john.doe",      // Replace with actual user ID from your session
    name: "John Doe",         // Replace with actual user name
    email: "john@example.com" // Replace with actual user email
};
```

### Step 2: Copy the Code

The example contains everything you need:
- Chat button styling
- Iframe container
- JavaScript for auto-login
- Error handling

### Step 3: Customize (Optional)

- Change button position/style
- Adjust iframe size
- Modify colors/theme
- Add custom error messages

---

## 🔑 API Endpoint

### `/api/chatbot-login` (POST)

Creates a session and returns JWT token for SSO.

**Request:**
```json
{
  "user_id": "john.doe",
  "name": "John Doe",
  "email": "john@example.com"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "session_created": true,
  "user_id": "john.doe",
  "name": "John Doe"
}
```

**Usage in your app:**
```javascript
const response = await fetch('https://chat.aichatbot.schemes.ddpdashboard.gov.in/api/chatbot-login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    credentials: 'include',
    body: JSON.stringify(userDetails)
});
const data = await response.json();
iframe.src = `https://chat.aichatbot.schemes.ddpdashboard.gov.in/aichat/sso?token=${data.token}`;
```

---

## 🔒 Security Notes

### Important: Get User Details from YOUR Session

**✅ Good:**
```javascript
// Your backend endpoint that validates YOUR session
fetch('/get-current-user')
  .then(r => r.json())
  .then(user => {
    // user details from YOUR authenticated session
    return fetch('/api/chatbot-login', {
      method: 'POST',
      body: JSON.stringify(user)
    });
  });
```

**❌ Bad:**
```javascript
// Hardcoded - anyone can change this!
const user = {user_id: "admin"}; // Don't do this!
```

### Production Checklist

- [ ] User details come from authenticated session
- [ ] HTTPS enabled (`secure: true`)
- [ ] `SameSite=None` in config.yaml
- [ ] `.env.production` has strong secret
- [ ] Test iframe embedding works
- [ ] Test on mobile devices

---

## 📚 Additional Documentation

- **Deployment:** See `../README_DEPLOYMENT.md`
- **Complete Overview:** See `../FINAL_SUMMARY.md`

---

## 🎉 That's It!

You now have a production-ready embedded chatbot with automatic SSO login. Just update the user details and integrate into your website!

**Questions?** Check the documentation files in the root directory.
