"""
app_simple_login.py - Simple Login Page with JWT Generation

This is a standalone login server that:
1. Shows a login form to collect user details
2. Generates JWT token server-side (secure)
3. Redirects to the chatbot with the token

Usage:
    python app_simple_login.py

Then open: http://localhost:5000
"""

from flask import Flask, render_template_string, request, redirect, jsonify
from flask_cors import CORS
import jwt
import time
import os
import yaml
from pathlib import Path

# --------------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "config.yaml"

def load_config():
    """Load configuration from YAML file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}
    
    # Get URLs from config.yaml or environment variables
    # Priority: env var > config.yaml > default
    urls = config.get('urls', {})
    default_chatbot_url = urls.get('chatbot_sso', 'http://localhost:8000/aichat/sso')
    
    return {
        'SSO_SECRET': os.getenv('SSO_SHARED_SECRET') or config.get('sso', {}).get('secret'),
        'SSO_ISSUER': os.getenv('SSO_EXPECT_ISS') or config.get('sso', {}).get('expect_issuer', 'ddpdashboard-aichatbot-portal'),
        'SSO_AUDIENCE': os.getenv('SSO_EXPECT_AUD') or config.get('sso', {}).get('expect_audience', 'aichat'),
        'CHATBOT_URL': os.getenv('CHATBOT_URL', default_chatbot_url),
        'LOGIN_URL': os.getenv('LOGIN_URL', urls.get('login', 'http://localhost:5000')),
        'TOKEN_EXPIRY': int(os.getenv('TOKEN_EXPIRY', '3600'))
    }

config = load_config()

if not config['SSO_SECRET']:
    raise RuntimeError("SSO_SHARED_SECRET must be set in config.yaml or as environment variable")

# --------------------------------------------------------------------------------------
# Flask App
# --------------------------------------------------------------------------------------
app = Flask(__name__)
CORS(app)

# --------------------------------------------------------------------------------------
# HTML Template
# --------------------------------------------------------------------------------------
LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>InsightDB AI Chatbot - Login</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .login-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 450px;
            padding: 40px;
            animation: slideUp 0.5s ease;
        }
        
        @keyframes slideUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .logo {
            text-align: center;
            margin-bottom: 32px;
        }
        
        .logo-icon {
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 20px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            margin-bottom: 16px;
        }
        
        h1 {
            color: #1e293b;
            font-size: 28px;
            margin-bottom: 8px;
            text-align: center;
        }
        
        .subtitle {
            color: #64748b;
            text-align: center;
            margin-bottom: 32px;
            font-size: 15px;
        }
        
        .form-group {
            margin-bottom: 24px;
        }
        
        label {
            display: block;
            color: #334155;
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 14px;
        }
        
        input {
            width: 100%;
            padding: 14px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 10px;
            font-size: 15px;
            transition: all 0.3s ease;
            font-family: inherit;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        input::placeholder {
            color: #94a3b8;
        }
        
        .btn-submit {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 8px;
        }
        
        .btn-submit:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
        }
        
        .btn-submit:active {
            transform: translateY(0);
        }
        
        .btn-submit:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .error-message {
            background: #fee2e2;
            color: #dc2626;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            display: none;
        }
        
        .error-message.show {
            display: block;
            animation: shake 0.5s ease;
        }
        
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-10px); }
            75% { transform: translateX(10px); }
        }
        
        .info-box {
            background: #f0f9ff;
            border: 1px solid #bae6fd;
            color: #0369a1;
            padding: 12px 16px;
            border-radius: 8px;
            margin-top: 20px;
            font-size: 13px;
            line-height: 1.5;
        }
        
        .required {
            color: #ef4444;
        }
        
        footer {
            text-align: center;
            color: white;
            margin-top: 24px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <div class="logo-icon">🤖</div>
            <h1>InsightDB AI Chatbot</h1>
            <p class="subtitle">Enter your details to start chatting</p>
        </div>
        
        <div id="error-message" class="error-message"></div>
        
        <form id="login-form" method="POST" action="/login">
            <div class="form-group">
                <label for="user_id">User ID <span class="required">*</span></label>
                <input 
                    type="text" 
                    id="user_id" 
                    name="user_id" 
                    placeholder="e.g., user123"
                    required
                    autocomplete="username"
                >
            </div>
            
            <div class="form-group">
                <label for="name">Full Name <span class="required">*</span></label>
                <input 
                    type="text" 
                    id="name" 
                    name="name" 
                    placeholder="e.g., John Doe"
                    required
                    autocomplete="name"
                >
            </div>
            
            <div class="form-group">
                <label for="email">Email Address <span class="required">*</span></label>
                <input 
                    type="email" 
                    id="email" 
                    name="email" 
                    placeholder="e.g., john@example.com"
                    required
                    autocomplete="email"
                >
            </div>
            
            <button type="submit" class="btn-submit">
                Continue to Chatbot →
            </button>
        </form>
        
        <div class="info-box">
            <strong>ℹ️ Note:</strong> Your information is used only for this session and is not stored permanently.
        </div>
    </div>
    
    <footer>
        <p>Powered by InsightDB</p>
    </footer>
    
    <script>
        // Show error message if present in URL
        const urlParams = new URLSearchParams(window.location.search);
        const error = urlParams.get('error');
        if (error) {
            const errorDiv = document.getElementById('error-message');
            errorDiv.textContent = decodeURIComponent(error);
            errorDiv.classList.add('show');
        }
    </script>
</body>
</html>
"""

# --------------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------------

@app.route('/')
def index():
    """Show login page."""
    return render_template_string(LOGIN_PAGE)

@app.route('/login', methods=['POST'])
def login():
    """Process login and redirect to chatbot with JWT token."""
    try:
        # Get form data
        user_id = request.form.get('user_id', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        
        # Validate inputs
        if not user_id or not name or not email:
            return redirect('/?error=Please fill in all required fields')
        
        # Generate JWT token
        now = int(time.time())
        payload = {
            'sub': user_id,
            'name': name,
            'email': email,
            'iss': config['SSO_ISSUER'],
            'aud': config['SSO_AUDIENCE'],
            'iat': now,
            'exp': now + config['TOKEN_EXPIRY']
        }
        
        token = jwt.encode(payload, config['SSO_SECRET'], algorithm='HS256')
        
        # Redirect to chatbot with token
        redirect_url = f"{config['CHATBOT_URL']}?token={token}"
        
        print(f"[LOGIN] User: {user_id} ({name}) - Token generated")
        
        return redirect(redirect_url)
        
    except Exception as e:
        print(f"[ERROR] Login failed: {e}")
        return redirect(f'/?error=Login failed. Please try again.')

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'simple-login',
        'chatbot_url': config['CHATBOT_URL']
    })

# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.getenv('LOGIN_PORT', '5000'))
    
    print("=" * 70)
    print("InsightDB Simple Login Server")
    print("=" * 70)
    print(f"Server running on: http://localhost:{port}")
    print(f"Chatbot URL: {config['CHATBOT_URL']}")
    print(f"SSO Issuer: {config['SSO_ISSUER']}")
    print(f"Token Expiry: {config['TOKEN_EXPIRY']} seconds")
    print("=" * 70)
    print("\nOpen http://localhost:5000 in your browser to login")
    print("\nPress Ctrl+C to stop")
    print("=" * 70)
    
    app.run(host='0.0.0.0', port=port, debug=True)
