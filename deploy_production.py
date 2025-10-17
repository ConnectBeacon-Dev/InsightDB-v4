#!/usr/bin/env python3
"""
Production Deployment Script for ConnectBeacon AI Chatbot
This script sets up environment variables and starts the servers
"""

import os
import sys
import secrets
import string
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent
CONFIG_FILE = REPO / ".env.production"

def generate_secret(length=64):
    """Generate a secure random secret"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def load_or_create_secret():
    """Load existing secret from .env.production or create a new one"""
    if CONFIG_FILE.exists():
        print(f"[INFO] Loading configuration from: {CONFIG_FILE}")
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('SSO_SHARED_SECRET='):
                    secret = line.split('=', 1)[1]
                    print("[OK] Using existing SSO_SHARED_SECRET")
                    return secret
    
    # Generate new secret
    print("[INFO] No existing secret found. Generating new one...")
    secret = generate_secret(64)
    
    # Save to file
    with open(CONFIG_FILE, 'w') as f:
        f.write(f"# ConnectBeacon Production Configuration\n")
        f.write(f"# Generated automatically - DO NOT COMMIT TO GIT\n\n")
        f.write(f"SSO_SHARED_SECRET={secret}\n")
        f.write(f"CHATBOT_URL=https://chat.connectbeacon.com/aichat/sso\n")
        f.write(f"LOGIN_URL=https://login.connectbeacon.com\n")
        f.write(f"SERVER_HOST=0.0.0.0\n")
        f.write(f"PORT=8000\n")
        f.write(f"LOGIN_PORT=5000\n")
        f.write(f"SSO_EXPECT_ISS=ddpdashboard-aichatbot-portal\n")
        f.write(f"SSO_EXPECT_AUD=aichat\n")
        f.write(f"TOKEN_EXPIRY=3600\n")
    
    print(f"[OK] New secret generated and saved to: {CONFIG_FILE}")
    print(f"[SECRET] {secret}")
    print("[IMPORTANT] Keep this secret secure and backed up!")
    
    return secret

def load_environment():
    """Load environment variables from .env.production and config.yaml"""
    if not CONFIG_FILE.exists():
        print(f"[ERROR] Configuration file not found: {CONFIG_FILE}")
        sys.exit(1)
    
    print(f"[INFO] Loading environment from: {CONFIG_FILE}")
    
    # Load from .env.production
    with open(CONFIG_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value
                if key != 'SSO_SHARED_SECRET':  # Don't print secret
                    print(f"  {key}={value}")
    
    # Also load URLs from config.yaml if not in environment
    config_yaml = REPO / "config.yaml"
    if config_yaml.exists():
        import yaml
        with open(config_yaml, 'r') as f:
            cfg = yaml.safe_load(f) or {}
            urls = cfg.get('urls', {})
            
            # Set URLs from config.yaml if not already in environment
            if 'LOGIN_URL' not in os.environ and urls.get('login'):
                os.environ['LOGIN_URL'] = urls['login']
                print(f"  LOGIN_URL={urls['login']} (from config.yaml)")
            
            if 'CHATBOT_URL' not in os.environ and urls.get('chatbot_sso'):
                os.environ['CHATBOT_URL'] = urls['chatbot_sso']
                print(f"  CHATBOT_URL={urls['chatbot_sso']} (from config.yaml)")

def validate_configuration():
    """Validate the configuration"""
    print("\n[INFO] Validating configuration...")
    
    # Check secret
    secret = os.environ.get('SSO_SHARED_SECRET')
    if not secret or len(secret) < 32:
        print("[ERROR] SSO_SHARED_SECRET is not set or too short!")
        sys.exit(1)
    
    # Check virtual environment
    venv_python = REPO / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        print(f"[ERROR] Virtual environment not found at: {venv_python}")
        sys.exit(1)
    
    # Check config.yaml
    config_yaml = REPO / "config.yaml"
    if not config_yaml.exists():
        print(f"[WARN] config.yaml not found at: {config_yaml}")
    
    print("[OK] Configuration validated")

def display_configuration():
    """Display the production configuration"""
    print("\n" + "="*70)
    print("PRODUCTION CONFIGURATION")
    print("="*70)
    print(f"  Login URL:    {os.environ.get('LOGIN_URL')}")
    print(f"  Chatbot URL:  {os.environ.get('CHATBOT_URL')}")
    print(f"  Login Port:   {os.environ.get('LOGIN_PORT')} (internal)")
    print(f"  Chatbot Port: {os.environ.get('PORT')} (internal)")
    print(f"  Token Expiry: {os.environ.get('TOKEN_EXPIRY')} seconds")
    print("="*70 + "\n")

def start_servers():
    """Start the production servers"""
    print("[INFO] Starting production servers...\n")
    
    launcher_script = REPO / "run_pipeline_and_serve.py"
    if not launcher_script.exists():
        print(f"[ERROR] Launcher script not found: {launcher_script}")
        sys.exit(1)
    
    # Start the launcher with --skip-etl and --detached flags
    venv_python = REPO / ".venv" / "Scripts" / "python.exe"
    cmd = [str(venv_python), str(launcher_script), "--skip-etl", "--detached"]
    
    try:
        result = subprocess.run(cmd, cwd=str(REPO), check=True)
        
        if result.returncode == 0:
            # Get configured URLs from environment
            login_url = os.environ.get('LOGIN_URL', 'http://localhost:5000')
            chatbot_url = os.environ.get('CHATBOT_URL', 'http://localhost:8000/aichat')
            login_port = os.environ.get('LOGIN_PORT', '5000')
            chatbot_port = os.environ.get('PORT', '8000')
            
            print("\n" + "="*70)
            print("SERVERS STARTED SUCCESSFULLY!")
            print("="*70)
            print("\nConfigured URLs:")
            print(f"  Login:   {login_url}")
            print(f"  Chatbot: {chatbot_url}")
            print("\nInternal URLs (Direct to Python servers):")
            print(f"  Login:   http://localhost:{login_port}")
            print(f"  Chatbot: http://localhost:{chatbot_port}")
            print("\nManagement:")
            print("  Stop servers: python stop_servers.py")
            print("  View logs:    Get-Content logs\\*.out -Wait")
            print("  Check PIDs:   Get-Content logs\\server.pids")
            print()
        else:
            print("\n[ERROR] Failed to start servers")
            print("Check logs in logs\\ directory")
            sys.exit(1)
            
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Failed to start servers: {e}")
        print("Check logs in logs\\ directory")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[ABORT] Interrupted by user")
        sys.exit(1)

def main():
    """Main deployment function"""
    print("="*70)
    print("ConnectBeacon AI Chatbot - Production Deployment")
    print("="*70)
    print()
    
    # Load or create secret
    secret = load_or_create_secret()
    
    # Load all environment variables
    load_environment()
    
    # Validate configuration
    validate_configuration()
    
    # Display configuration
    display_configuration()
    
    # Start servers
    start_servers()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[ABORT] Deployment interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
